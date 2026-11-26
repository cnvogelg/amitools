"""Run the original AmigaOS 3.2.3 ``WBLoad`` command (see test/cli/README.md).

``WBLoad PROG`` launches a Workbench program.  It needs the Workbench, so only
the argument check is exercised here: ``WBLoad`` without a program prints
``ERROR_REQUIRED_ARG_MISSING`` and returns 10.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

WBLOAD_SHA1 = "12aceb32c2125442f6a5f6322c17fdbf6c8798fb"


def cli_wbload_missing_arg_test(vrun):
    """``WBLoad`` without a program reports a missing argument."""
    skip_if_cmd_missing(vrun, "WBLoad", WBLOAD_SHA1)
    stdout, stderr = run_cli_rc(vrun, "WBLoad", expect_rc=10)
    assert stdout == ["ERROR_REQUIRED_ARG_MISSING"]
    assert stderr == []
