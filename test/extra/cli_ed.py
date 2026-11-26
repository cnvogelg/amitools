"""Run the original AmigaOS 3.2.3 ``Ed`` command (see test/cli/README.md).

``Ed FILE`` is a full-screen editor; it needs a window (RAW: console), so only
the argument check is exercised here.  ``Ed`` without a file prints
``ERROR_REQUIRED_ARG_MISSING`` and returns 10.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

ED_SHA1 = "d19392f9e669eaee3aa41edbebc5d2cd46ac10f9"


def cli_ed_missing_arg_test(vrun):
    """``Ed`` without a file reports a missing argument."""
    skip_if_cmd_missing(vrun, "Ed", ED_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Ed", expect_rc=10)
    assert stdout == ["ERROR_REQUIRED_ARG_MISSING"]
    assert stderr == []
