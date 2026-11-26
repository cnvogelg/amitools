"""Run the original AmigaOS 3.2.3 ``ROMReserveLow`` command (see test/cli/README.md).

``ROMReserveLow`` sets, checks or removes a low-memory reservation cookie used
by the ROM.  Each test is a fresh ``vamos`` run, so ``CHECK`` starts from the
unset state.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

ROMRESERVELOW_SHA1 = "3066d15ae861c8eb60b523a6c043330dc59650e6"


def cli_romreservelow_set_test(vrun):
    """``ROMReserveLow`` sets the reservation cookie."""
    skip_if_cmd_missing(vrun, "ROMReserveLow", ROMRESERVELOW_SHA1)
    stdout, stderr = run_cli_rc(vrun, "ROMReserveLow")
    assert stdout == ["Rom low memory reservation cookie set"]
    assert stderr == []


def cli_romreservelow_check_test(vrun):
    """``ROMReserveLow CHECK`` reports the (unset) cookie."""
    skip_if_cmd_missing(vrun, "ROMReserveLow", ROMRESERVELOW_SHA1)
    stdout, stderr = run_cli_rc(vrun, "ROMReserveLow", "CHECK", expect_rc=20)
    assert stdout == ["Rom low memory reservation cookie not set"]
    assert stderr == []


def cli_romreservelow_remove_test(vrun):
    """``ROMReserveLow REMOVE`` removes the reservation cookie."""
    skip_if_cmd_missing(vrun, "ROMReserveLow", ROMRESERVELOW_SHA1)
    stdout, stderr = run_cli_rc(vrun, "ROMReserveLow", "REMOVE", expect_rc=20)
    assert stdout == ["Rom low memory reservation cookie removed"]
    assert stderr == []


def cli_romreservelow_quiet_test(vrun):
    """``ROMReserveLow QUIET`` sets the cookie without printing anything."""
    skip_if_cmd_missing(vrun, "ROMReserveLow", ROMRESERVELOW_SHA1)
    stdout, stderr = run_cli_rc(vrun, "ROMReserveLow", "QUIET")
    assert stdout == []
    assert stderr == []
