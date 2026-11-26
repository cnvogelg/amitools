"""Run the original AmigaOS 3.2.3 ``Copy`` command (see test/cli/README.md)."""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

COPY_SHA1 = "8d17b03b0cb92608e31c3da203d1afdf5d6c0a61"


def cli_copy_file_test(vrun, tmp_path):
    """``Copy <src> <dst>`` duplicates a file."""
    skip_if_cmd_missing(vrun, "Copy", COPY_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Copy", "work:in.txt", "work:copy.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    assert (tmp_path / "copy.txt").read_text() == "hello\nworld\n"


def cli_copy_into_subdir_test(vrun, tmp_path):
    """``Copy`` accepts a destination inside a subdirectory."""
    skip_if_cmd_missing(vrun, "Copy", COPY_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Copy", "work:in.txt", "work:sub/copy.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    assert (tmp_path / "sub" / "copy.txt").read_text() == "hello\nworld\n"


def cli_copy_missing_test(vrun, tmp_path):
    """A missing source file is reported."""
    skip_if_cmd_missing(vrun, "Copy", COPY_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "Copy",
        "work:missing.txt",
        "work:copy.txt",
        expect_rc=5,
        vargs=work_vargs(tmp_path),
    )
    assert stdout == ["Can't open missing.txt for input - ERROR_OBJECT_NOT_FOUND"]
    assert stderr == []
