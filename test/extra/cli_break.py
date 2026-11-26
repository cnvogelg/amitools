"""Run the original AmigaOS 3.2.3 ``Break`` command (see test/cli/README.md).

``Break <process>`` sends a signal to a CLI process.  vamos has no CLI process
table, so a numeric process id is always reported as missing; this exercises the
command's error path.  Breaking a *real* task needs a shell session (see the
optional ``cli_shell.py``).
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

BREAK_SHA1 = "04c35975cbf7a0790a90bd7d7927c2cdbdb8d233"


def cli_break_missing_proc_test(vrun):
    """``Break 1`` reports that process 1 does not exist."""
    skip_if_cmd_missing(vrun, "Break", BREAK_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Break", "1", expect_rc=20)
    assert stdout == ["Process 1 does not exist", "ERROR_OBJECT_NOT_FOUND"]
    assert stderr == []


def cli_break_missing_name_test(vrun):
    """``Break NAME=foo`` reports that task ``foo`` does not exist."""
    skip_if_cmd_missing(vrun, "Break", BREAK_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Break", "NAME=foo", expect_rc=20)
    assert stdout == ["Process foo does not exist", "ERROR_OBJECT_NOT_FOUND"]
    assert stderr == []
