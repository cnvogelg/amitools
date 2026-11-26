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
