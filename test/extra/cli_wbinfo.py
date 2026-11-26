"""Run the original AmigaOS 3.2.3 ``WBInfo`` command (see test/cli/README.md).

``WBInfo`` prints Workbench icon information; opening a real icon file needs
Workbench and crashes under ``vamos``, so only the argument check is exercised
here.  ``WBInfo`` without a file prints ``WBINFO: ERROR_REQUIRED_ARG_MISSING``
and returns 20.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

WBINFO_SHA1 = "5b21931ef82f92abad4bb154b84a979700c3cc1b"


def cli_wbinfo_missing_arg_test(vrun):
    """``WBInfo`` without a file reports a missing argument."""
    skip_if_cmd_missing(vrun, "WBInfo", WBINFO_SHA1)
    stdout, stderr = run_cli_rc(vrun, "WBInfo", expect_rc=20)
    assert stdout == ["WBINFO: ERROR_REQUIRED_ARG_MISSING"]
    assert stderr == []
