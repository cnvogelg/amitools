"""Run the original AmigaOS 3.2.3 ``RemRAD`` command (see test/cli/README.md).

``RemRAD`` removes a Recoverable RAM Disk.  ``vamos`` does not provide one, so
the default unit 0 is reported as not mounted and a device argument is checked
against the mounted volumes.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

REMRAD_SHA1 = "0485fdf28e02a901d45aabc5e1d3ac55623fd011"


def cli_remrad_default_test(vrun):
    """``RemRAD`` reports that unit 0 has no Recoverable Ram Drive."""
    skip_if_cmd_missing(vrun, "RemRAD", REMRAD_SHA1)
    stdout, stderr = run_cli_rc(vrun, "RemRAD", expect_rc=10)
    assert stdout == ["No Recoverable Ram Drive Mounted on Unit 0"]
    assert stderr == []


def cli_remrad_device_test(vrun):
    """``RemRAD DEVICE ram:`` reports that ``ram:`` is not a Ram Drive."""
    skip_if_cmd_missing(vrun, "RemRAD", REMRAD_SHA1)
    stdout, stderr = run_cli_rc(vrun, "RemRAD", "DEVICE", "ram:", expect_rc=10)
    assert stdout == ["ram: is not a Recoverable Ram Drive"]
    assert stderr == []


def cli_remrad_missing_arg_test(vrun):
    """``RemRAD DEVICE`` without a value reports ``ERROR_KEY_NEEDS_ARG``."""
    skip_if_cmd_missing(vrun, "RemRAD", REMRAD_SHA1)
    stdout, stderr = run_cli_rc(vrun, "RemRAD", "DEVICE", expect_rc=20)
    assert stdout == ["ERROR_KEY_NEEDS_ARG"]
    assert stderr == []
