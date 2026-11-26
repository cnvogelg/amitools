"""Run the original AmigaOS 3.2.3 ``Delete`` command (see test/cli/README.md)."""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

DELETE_SHA1 = "030191ef5fdfb185fca182bd286de30b39ae89bd"


def cli_delete_file_test(vrun, tmp_path):
    """``Delete <file>`` removes a file and reports it."""
    skip_if_cmd_missing(vrun, "Delete", DELETE_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Delete", "work:del.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == ["work:del.txt  Deleted"]
    assert stderr == []
    assert not (tmp_path / "del.txt").exists()


def cli_delete_multiple_test(vrun, tmp_path):
    """``Delete`` accepts several files (``FILE/A``)."""
    skip_if_cmd_missing(vrun, "Delete", DELETE_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Delete", "work:del.txt", "work:ren.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == ["work:del.txt  Deleted", "work:ren.txt  Deleted"]
    assert stderr == []
    assert not (tmp_path / "del.txt").exists()
    assert not (tmp_path / "ren.txt").exists()


def cli_delete_missing_test(vrun, tmp_path):
    """A missing file is reported."""
    skip_if_cmd_missing(vrun, "Delete", DELETE_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Delete", "work:missing.txt", expect_rc=5, vargs=work_vargs(tmp_path)
    )
    assert stdout == ["No file to delete"]
    assert stderr == []
