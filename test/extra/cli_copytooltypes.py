"""Run the original AmigaOS 3.2.3 ``CopyTooltypes`` command (see test/cli/README.md).

``CopyTooltypes FROM TO`` copies the Tool Types between two ``.info`` files.
The scratch tree has no icon files, so the command reports that it cannot open
the source icon; ``QUIET`` suppresses the progress line but keeps the error.
"""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

COPYTOOLTYPES_SHA1 = "09dbf313267f2d4983c0abf381069e289508d4c6"

_NO_ICON = "Cannot access source icon: ERROR_OBJECT_NOT_FOUND"


def cli_copytooltypes_missing_icon_test(vrun, tmp_path):
    """``CopyTooltypes FROM TO`` reports a missing source icon."""
    skip_if_cmd_missing(vrun, "CopyTooltypes", COPYTOOLTYPES_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "CopyTooltypes",
        "work:in.txt",
        "work:out.txt",
        expect_rc=20,
        vargs=work_vargs(tmp_path),
    )
    assert stdout == [
        "Copying Tool Types from work:in.txt.info to work:out.txt.info ...",
        _NO_ICON,
    ]
    assert stderr == []


def cli_copytooltypes_quiet_test(vrun, tmp_path):
    """``CopyTooltypes ... QUIET`` drops the progress line but keeps the error."""
    skip_if_cmd_missing(vrun, "CopyTooltypes", COPYTOOLTYPES_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "CopyTooltypes",
        "work:in.txt",
        "work:out.txt",
        "QUIET",
        expect_rc=20,
        vargs=work_vargs(tmp_path),
    )
    assert stdout == [_NO_ICON]
    assert stderr == []
