"""Run the original AmigaOS 3.2.3 ``Wait`` command (see test/cli/README.md).

``Wait`` sleeps for a number of ticks (or seconds with ``SECS``).  ``0`` makes
it return immediately, so the tests do not actually wait.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

WAIT_SHA1 = "0c16d8160a37575288310a4bbb86b9611666a5cf"


def cli_wait_ticks_test(vrun):
    """``Wait 0`` returns immediately."""
    skip_if_cmd_missing(vrun, "Wait", WAIT_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Wait", "0")
    assert stdout == []
    assert stderr == []


def cli_wait_secs_test(vrun):
    """``Wait SECS 0`` is the seconds form and also returns immediately."""
    skip_if_cmd_missing(vrun, "Wait", WAIT_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Wait", "SECS", "0")
    assert stdout == []
    assert stderr == []
