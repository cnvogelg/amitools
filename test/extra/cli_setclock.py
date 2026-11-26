"""Run the original AmigaOS 3.2.3 ``SetClock`` command (see test/cli/README.md).

``SetClock`` reads or writes a battery-backed real-time clock.  ``vamos`` has
no such clock, so ``LOAD``, ``SAVE`` and ``RESET`` all fail with
``Can't find battery-backed up clock``.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

SETCLOCK_SHA1 = "abaff8bfc1a1d798aa3fc70499beb2ae075dd48a"

_NO_CLOCK = "Can't find battery-backed up clock"


def cli_setclock_load_test(vrun):
    """``SetClock LOAD`` cannot find a battery-backed up clock."""
    skip_if_cmd_missing(vrun, "SetClock", SETCLOCK_SHA1)
    stdout, stderr = run_cli_rc(vrun, "SetClock", "LOAD", expect_rc=20)
    assert stdout == [_NO_CLOCK]
    assert stderr == []


def cli_setclock_save_test(vrun):
    """``SetClock SAVE`` cannot find a battery-backed up clock."""
    skip_if_cmd_missing(vrun, "SetClock", SETCLOCK_SHA1)
    stdout, stderr = run_cli_rc(vrun, "SetClock", "SAVE", expect_rc=20)
    assert stdout == [_NO_CLOCK]
    assert stderr == []


def cli_setclock_reset_test(vrun):
    """``SetClock RESET`` cannot find a battery-backed up clock."""
    skip_if_cmd_missing(vrun, "SetClock", SETCLOCK_SHA1)
    stdout, stderr = run_cli_rc(vrun, "SetClock", "RESET", expect_rc=20)
    assert stdout == [_NO_CLOCK]
    assert stderr == []


def cli_setclock_badarg_test(vrun):
    """An unknown keyword is rejected as a superfluous argument."""
    skip_if_cmd_missing(vrun, "SetClock", SETCLOCK_SHA1)
    stdout, stderr = run_cli_rc(vrun, "SetClock", "NOPE", expect_rc=20)
    assert stdout == ["ERROR_TOO_MANY_ARGS"]
    assert stderr == []
