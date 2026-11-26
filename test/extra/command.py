"""Run Python commands (``vamos.cmdcore``) end to end.

A command is a ``*.py`` file whose first line is a Python shebang. Vamos
presents it to the m68k side as a minimal stub, so it runs like any other
binary. These tests use host files under ``tmp_path`` (mapped through the
``root=/`` volume of ``test.vamosrc``) and need no cross compiler.
"""

import os

SHEBANG = "#!/usr/bin/env python3\n"


def _make_cmd(tmp_path, name, body):
    p = tmp_path / (name + ".py")
    p.write_text(SHEBANG + body)
    return str(p)


def _ami_cwd(tmp_path):
    """the ``root:`` Amiga path of a host tmp dir (test.vamosrc maps root=/)"""
    return "root:" + str(tmp_path).lstrip("/")


def command_run_binary_test(vrun, tmp_path):
    """run a .py directly as a binary and read its exit code"""
    cmd = _make_cmd(
        tmp_path,
        "hello",
        "def main(ctx, arg_line, prog_name):\n"
        "    ctx.stdout.writeln('hello %s' % prog_name)\n"
        "    return 7\n",
    )
    retcode, stdout, stderr = vrun.run_prog(cmd)
    assert retcode == 7
    assert stdout == ["hello hello"]
    assert stderr == []


def command_run_binary_args_test(vrun, tmp_path):
    """the command receives its argument line and prog name

    Like a real AmigaDOS program the argument line ends with a newline, so
    the command strips it for display.
    """
    cmd = _make_cmd(
        tmp_path,
        "args",
        "def main(ctx, arg_line, prog_name):\n"
        "    ctx.stdout.writeln('prog=%s' % prog_name)\n"
        "    ctx.stdout.writeln('args=%s' % arg_line.rstrip())\n"
        "    return 0\n",
    )
    retcode, stdout, stderr = vrun.run_prog(cmd, "foo", "bar")
    assert retcode == 0
    assert stdout == ["prog=args", "args=foo bar"]
    assert stderr == []


def command_run_binary_error_test(vrun, tmp_path):
    """an exception in main() yields a non-zero exit code"""
    cmd = _make_cmd(
        tmp_path,
        "boom",
        "def main(ctx, arg_line, prog_name):\n    raise ValueError('nope')\n",
    )
    retcode, stdout, stderr = vrun.run_prog(cmd)
    assert retcode != 0
    assert stdout == []


def command_binary_executable_gate_test(vrun, tmp_path):
    """a bare command name on the command path needs the host execute bit"""
    cmd = _make_cmd(
        tmp_path,
        "gate",
        "def main(ctx, arg_line, prog_name):\n"
        "    ctx.stdout.writeln('gate ran')\n"
        "    return 0\n",
    )
    cwd = _ami_cwd(tmp_path)
    # not executable: the command is not picked up
    os.chmod(cmd, 0o644)
    retcode, stdout, stderr = vrun.run_prog("gate.py", vargs=["--cwd", cwd])
    assert retcode != 0
    assert stdout == []
    # executable: the command runs
    os.chmod(cmd, 0o755)
    retcode, stdout, stderr = vrun.run_prog("gate.py", vargs=["--cwd", cwd])
    assert retcode == 0
    assert stdout == ["gate ran"]
    assert stderr == []


def command_binary_explicit_no_gate_test(vrun, tmp_path):
    """an explicit path is loaded without the execute gate"""
    cmd = _make_cmd(
        tmp_path,
        "plain",
        "def main(ctx, arg_line, prog_name):\n"
        "    ctx.stdout.writeln('plain ran')\n"
        "    return 0\n",
    )
    os.chmod(cmd, 0o644)
    retcode, stdout, stderr = vrun.run_prog(cmd)
    assert retcode == 0
    assert stdout == ["plain ran"]
    assert stderr == []


# ----- resident commands (driven through the real shell) -----

# a stock Shell-Seg fixture (see test/shell-seg/README.md); the tests skip when
# it was not extracted locally. 132 is its own endcli return code.
SHELL_SEG_DIR = "shell-seg"
SHELL_SEG_NAME = "Shell-Seg-47.48"
SHELL_SEG_RETCODE = 132
PROMPT = "\x0f0.SYS:> "


def _check_shell_seg(vrun):
    vrun.skip_if_prog_not_available(os.path.join(SHELL_SEG_DIR, SHELL_SEG_NAME))
    vol_arg = "-Vseg:" + SHELL_SEG_DIR
    if vol_arg not in vrun.vamos_args:
        vrun.add_volume_or_skip("seg", SHELL_SEG_DIR)


def command_resident_shell_test(vrun, tmp_path):
    """a --resident-dir command is found and run by the stock shell"""
    _check_shell_seg(vrun)
    (tmp_path / "hello.py").write_text(
        "def main(ctx, arg_line, prog_name):\n"
        "    ctx.stdout.writeln('resident %s' % prog_name)\n"
        "    return 5\n"
    )
    seg = "seg:" + SHELL_SEG_NAME
    retcode, stdout, stderr = vrun.run_prog(
        seg,
        vargs=["-x", "--shell-bin", seg, "--resident-dir", str(tmp_path)],
        stdin="hello\nendcli\n",
    )
    assert stdout == [PROMPT + "resident hello", PROMPT + "PROCESS 0 ENDING"]
    assert stderr == []
    assert retcode == SHELL_SEG_RETCODE


def command_resident_shell_args_test(vrun, tmp_path):
    """the resident command receives the shell command line in A0/D0"""
    _check_shell_seg(vrun)
    (tmp_path / "echoargs.py").write_text(
        "def main(ctx, arg_line, prog_name):\n"
        "    ctx.stdout.writeln('args=%s' % arg_line.rstrip())\n"
        "    return 0\n"
    )
    seg = "seg:" + SHELL_SEG_NAME
    retcode, stdout, stderr = vrun.run_prog(
        seg,
        vargs=["-x", "--shell-bin", seg, "--resident-dir", str(tmp_path)],
        stdin="echoargs one two\nendcli\n",
    )
    assert stdout == [PROMPT + "args=one two", PROMPT + "PROCESS 0 ENDING"]
    assert stderr == []
    assert retcode == SHELL_SEG_RETCODE


def command_resident_shell_error_test(vrun, tmp_path):
    """a command that raises does not take the shell down with it"""
    _check_shell_seg(vrun)
    (tmp_path / "boom.py").write_text(
        "def main(ctx, arg_line, prog_name):\n    raise ValueError('nope')\n"
    )
    seg = "seg:" + SHELL_SEG_NAME
    retcode, stdout, stderr = vrun.run_prog(
        seg,
        vargs=["-x", "--shell-bin", seg, "--resident-dir", str(tmp_path)],
        stdin="boom\nendcli\n",
    )
    # the shell survives the failing command and reaches its own endcli
    assert stdout[-1].endswith("PROCESS 0 ENDING")
    assert retcode == SHELL_SEG_RETCODE
