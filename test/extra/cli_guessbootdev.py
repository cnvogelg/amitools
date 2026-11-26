"""Run the original AmigaOS 3.2.3 ``GuessBootDev`` command (see test/cli/README.md).

``GuessBootDev`` tries to name the volume the system booted from.  Under
``vamos`` the boot volume is ``SYS:``; the command prints it and sets the
condition flag (return code 20).
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

GUESSBOOTDEV_SHA1 = "39d5acd6af505423330ed25b20e1862277e33849"


def cli_guessbootdev_test(vrun):
    """``GuessBootDev`` prints the guessed boot device and sets the condition
    flag."""
    skip_if_cmd_missing(vrun, "GuessBootDev", GUESSBOOTDEV_SHA1)
    stdout, stderr = run_cli_rc(vrun, "GuessBootDev", expect_rc=20)
    assert stdout == ["SYS:"]
    assert stderr == []


def cli_guessbootdev_name_test(vrun):
    """``BOOTDISKNAME=`` only names the variable to set; the device is still
    printed."""
    skip_if_cmd_missing(vrun, "GuessBootDev", GUESSBOOTDEV_SHA1)
    stdout, stderr = run_cli_rc(vrun, "GuessBootDev", "BOOTDISKNAME=BD", expect_rc=20)
    assert stdout == ["SYS:"]
    assert stderr == []
