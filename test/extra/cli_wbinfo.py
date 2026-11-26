"""Run the original AmigaOS 3.2.3 ``WBInfo`` command (see test/cli/README.md).

``WBInfo`` opens the Workbench "Information" window for a file, drawer or
volume.  The window itself needs a running Workbench, but ``vamos`` now stubs
``workbench.library/WBInfo`` (see ``test/unit/lib_workbench.py``) so the
command completes.  Without a file it prints
``WBINFO: ERROR_REQUIRED_ARG_MISSING`` and returns 20.
"""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

WBINFO_SHA1 = "5b21931ef82f92abad4bb154b84a979700c3cc1b"


def cli_wbinfo_missing_arg_test(vrun):
    """``WBInfo`` without a file reports a missing argument."""
    skip_if_cmd_missing(vrun, "WBInfo", WBINFO_SHA1)
    stdout, stderr = run_cli_rc(vrun, "WBInfo", expect_rc=20)
    assert stdout == ["WBINFO: ERROR_REQUIRED_ARG_MISSING"]
    assert stderr == []


def cli_wbinfo_file_test(vrun, tmp_path):
    """``WBInfo FILE=<file>`` completes (the info window is stubbed)."""
    skip_if_cmd_missing(vrun, "WBInfo", WBINFO_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "WBInfo", "FILE=work:in.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []


def cli_wbinfo_drawer_test(vrun, tmp_path):
    """``WBInfo DRAWER=<dir>`` completes for an existing drawer."""
    skip_if_cmd_missing(vrun, "WBInfo", WBINFO_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "WBInfo", "DRAWER=work:sub", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []


def cli_wbinfo_missing_test(vrun, tmp_path):
    """A missing file is reported before the info window is opened."""
    skip_if_cmd_missing(vrun, "WBInfo", WBINFO_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "WBInfo",
        "FILE=work:missing.txt",
        expect_rc=10,
        vargs=work_vargs(tmp_path),
    )
    assert stdout == ["WBINFO: ERROR_OBJECT_NOT_FOUND"]
    assert stderr == []
