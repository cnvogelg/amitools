"""Run Python commands (``vamos.cmdcore``) end to end.

A command is a ``*.py`` file whose first line is a Python shebang. Vamos
presents it to the m68k side as a minimal stub, so it runs like any other
binary. These tests use host files under ``tmp_path`` (mapped through the
``root=/`` volume of ``test.vamosrc``) and need no cross compiler.
"""

import os

from amitools.vamos.cmdcore.version import get_amitools_version

SHEBANG = "#!/usr/bin/env python3\n"

# the sample command fixtures (test/command/), resolved from this file so the
# tests work regardless of the pytest working directory
COMMAND_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "command")
)


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


# ----- the sample fixtures (test/command/) run directly as binaries -----


def command_samples_binary_test(vrun):
    """run the sample fixtures directly as binaries and read their exit codes"""
    retcode, stdout, stderr = vrun.run_prog(os.path.join(COMMAND_DIR, "hello.py"))
    assert retcode == 0
    assert stdout == ["hello from hello"]
    assert stderr == []

    retcode, stdout, stderr = vrun.run_prog(os.path.join(COMMAND_DIR, "exit7.py"))
    assert retcode == 7
    assert stdout == []

    retcode, stdout, stderr = vrun.run_prog(
        os.path.join(COMMAND_DIR, "args.py"), "one", "two"
    )
    assert retcode == 0
    assert stdout == ["prog=args", "args=one two"]
    assert stderr == []


def command_samples_proxy_test(vrun):
    """the sample fixtures reach the dos and exec library proxies"""
    retcode, stdout, stderr = vrun.run_prog(os.path.join(COMMAND_DIR, "dosproxy.py"))
    assert retcode == 0
    assert stdout == ["ioerr=123", "output=ok"]
    assert stderr == []

    retcode, stdout, stderr = vrun.run_prog(os.path.join(COMMAND_DIR, "execproxy.py"))
    assert retcode == 0
    assert stdout == ["alloc=ok"]
    assert stderr == []


def command_ram_gate_test(vrun):
    """a Python command on RAM: needs the Amiga ``s`` bit (non-hostfs gate)

    ``ramgate.py`` writes a command to RAM: and runs it with
    ``SystemTagList()``. Run as a binary (not from the shell, which would
    forward to itself) SystemTagList() resolves the bare name through the
    command path, so the gate is applied. With the ``s`` bit the command runs,
    without it the load is refused.
    """
    cmd = os.path.join(COMMAND_DIR, "ramgate.py")
    # the script bit marks the RAM: command executable
    retcode, stdout, stderr = vrun.run_prog(
        cmd, "gated.py", "script", vargs=["--cwd", "ram:"]
    )
    assert retcode == 0
    assert stdout == ["ram command ran", "rc=0"]
    assert stderr == []
    # without the script bit the command is blocked (SystemTagList -> -1)
    retcode, stdout, stderr = vrun.run_prog(
        cmd, "plain.py", "plain", vargs=["--cwd", "ram:"]
    )
    assert retcode == 0
    assert stdout == ["rc=4294967295"]
    # the gate refuses the load and logs why
    assert any("failed loading binary: plain.py" in line for line in stderr)


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


def _run_shell(vrun, stdin, resident_dir=None):
    """run the stock shell and feed it ``stdin``; returns (rc, out, err)"""
    _check_shell_seg(vrun)
    seg = "seg:" + SHELL_SEG_NAME
    vargs = ["-x", "--shell-bin", seg]
    if resident_dir is not None:
        vargs += ["--resident-dir", resident_dir]
    return vrun.run_prog(seg, vargs=vargs, stdin=stdin)


def command_samples_hello_shell_test(vrun):
    """the hello sample runs as a resident command in the stock shell"""
    retcode, stdout, stderr = _run_shell(vrun, "hello\nendcli\n", COMMAND_DIR)
    assert stdout == [PROMPT + "hello from hello", PROMPT + "PROCESS 0 ENDING"]
    assert stderr == []
    assert retcode == SHELL_SEG_RETCODE


def command_samples_args_shell_test(vrun):
    """the args sample sees the shell command line and the program name"""
    retcode, stdout, stderr = _run_shell(vrun, "args one two\nendcli\n", COMMAND_DIR)
    assert stdout == [
        PROMPT + "prog=args",
        "args=one two",
        PROMPT + "PROCESS 0 ENDING",
    ]
    assert stderr == []
    assert retcode == SHELL_SEG_RETCODE


def command_samples_proxy_shell_test(vrun):
    """the proxy samples reach dos and exec from the shell"""
    retcode, stdout, stderr = _run_shell(vrun, "dosproxy\nendcli\n", COMMAND_DIR)
    assert stdout == [PROMPT + "ioerr=123", "output=ok", PROMPT + "PROCESS 0 ENDING"]
    assert stderr == []
    assert retcode == SHELL_SEG_RETCODE

    retcode, stdout, stderr = _run_shell(vrun, "execproxy\nendcli\n", COMMAND_DIR)
    assert stdout == [PROMPT + "alloc=ok", PROMPT + "PROCESS 0 ENDING"]
    assert stderr == []
    assert retcode == SHELL_SEG_RETCODE


def command_samples_exit7_shell_test(vrun):
    """a command's non-zero exit code does not disturb the shell"""
    retcode, stdout, stderr = _run_shell(vrun, "exit7\nendcli\n", COMMAND_DIR)
    assert stdout[-1].endswith("PROCESS 0 ENDING")
    assert retcode == SHELL_SEG_RETCODE


def command_resident_shell_error_test(vrun, tmp_path):
    """a command that raises does not take the shell down with it"""
    (tmp_path / "boom.py").write_text(
        "def main(ctx, arg_line, prog_name):\n    raise ValueError('nope')\n"
    )
    retcode, stdout, stderr = _run_shell(vrun, "boom\nendcli\n", str(tmp_path))
    # the shell survives the failing command and reaches its own endcli
    assert stdout[-1].endswith("PROCESS 0 ENDING")
    assert retcode == SHELL_SEG_RETCODE


# ----- built-in internal commands -----


def command_internal_vamos_version_test(vrun):
    """the built-in vamos command is available without any --resident-dir"""
    retcode, stdout, stderr = _run_shell(vrun, "vamos version\nendcli\n")
    assert stdout == [PROMPT + get_amitools_version(), PROMPT + "PROCESS 0 ENDING"]
    assert stderr == []
    assert retcode == SHELL_SEG_RETCODE


def command_internal_vamos_unknown_test(vrun):
    """an unknown subcommand prints usage and does not end the shell"""
    retcode, stdout, stderr = _run_shell(vrun, "vamos bogus\nendcli\n")
    assert any("unknown subcommand 'bogus'" in line for line in stdout)
    assert stdout[-1].endswith("PROCESS 0 ENDING")
    assert retcode == SHELL_SEG_RETCODE


def command_internal_disabled_test(vrun):
    """--no-internal-commands drops the built-in vamos command"""
    _check_shell_seg(vrun)
    seg = "seg:" + SHELL_SEG_NAME
    retcode, stdout, stderr = vrun.run_prog(
        seg,
        vargs=["-x", "--shell-bin", seg, "--no-internal-commands"],
        stdin="vamos version\nendcli\n",
    )
    assert any("Unknown command" in line for line in stdout)
    assert stdout[-1].endswith("PROCESS 0 ENDING")
    assert retcode == SHELL_SEG_RETCODE


def command_internal_collision_test(vrun, tmp_path):
    """a --resident-dir command overrides a built-in of the same name"""
    (tmp_path / "vamos.py").write_text(
        "def main(ctx, arg_line, prog_name):\n"
        "    ctx.stdout.writeln('user vamos')\n"
        "    return 0\n"
    )
    retcode, stdout, stderr = _run_shell(vrun, "vamos version\nendcli\n", str(tmp_path))
    assert stdout == [PROMPT + "user vamos", PROMPT + "PROCESS 0 ENDING"]
    assert stderr == []
    assert retcode == SHELL_SEG_RETCODE
