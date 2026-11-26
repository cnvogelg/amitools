"""Run the original AmigaOS 3.2.3 ``Filenote`` command (see test/cli/README.md).

The host file systems do not store AmigaDOS file comments, so setting a note
succeeds but reading it back does not; the round-trip test is ``xfail``.
"""

import pytest

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

FILENOTE_SHA1 = "43c8a7f8840539b44050a933280d2b56845a7812"


def cli_filenote_set_test(vrun, tmp_path):
    """``Filenote <file> <note>`` sets a file's comment."""
    skip_if_cmd_missing(vrun, "Filenote", FILENOTE_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Filenote", "work:in.txt", "a note", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []


def cli_filenote_missing_test(vrun, tmp_path):
    """A missing file is reported with the DOS error name."""
    skip_if_cmd_missing(vrun, "Filenote", FILENOTE_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "Filenote",
        "work:missing.txt",
        "a note",
        expect_rc=20,
        vargs=work_vargs(tmp_path),
    )
    assert stdout == ["ERROR_OBJECT_NOT_FOUND"]
    assert stderr == []


@pytest.mark.xfail(
    reason="host file systems do not store AmigaDOS file comments", strict=True
)
def cli_filenote_roundtrip_test(vrun, tmp_path):
    """``Filenote <file>`` displays the comment that was set before."""
    skip_if_cmd_missing(vrun, "Filenote", FILENOTE_SHA1)
    make_work_tree(tmp_path)
    run_cli_rc(vrun, "Filenote", "work:in.txt", "a note", vargs=work_vargs(tmp_path))
    stdout, stderr = run_cli_rc(
        vrun, "Filenote", "work:in.txt", vargs=work_vargs(tmp_path)
    )
    assert "a note" in "\n".join(stdout)
    assert stderr == []
