"""Run the original AmigaOS 3.2.3 ``Version`` command (see test/cli/README.md).

``Version`` prints the ``$VER:`` string of an AmigaOS binary.  It is the pilot
module for the CLI test harness: it exercises the ``cli:`` volume, the shared
``cli_util`` helpers and the ``skip_if_cmd_missing`` pattern.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

VERSION_SHA1 = "359f76f5843dee097c15f4bffce678a7c70e8d45"


def cli_version_self_test(vrun):
    """``Version <binary>`` prints the binary's own version."""
    skip_if_cmd_missing(vrun, "Version", VERSION_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Version", "cli:C/Version")
    assert stdout == ["version 47.3"]
    assert stderr == []


def cli_version_full_test(vrun):
    """``Version <binary> FULL`` adds the build date."""
    skip_if_cmd_missing(vrun, "Version", VERSION_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Version", "cli:C/Version", "FULL")
    assert stdout == ["version 47.3 (01/31/21)"]
    assert stderr == []


def cli_version_missing_test(vrun):
    """``Version`` without a file cannot find any version information."""
    skip_if_cmd_missing(vrun, "Version", VERSION_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Version", expect_rc=20)
    assert stdout == ["Kickstart 47.0, Could not find version information for ''"]
    assert stderr == []
