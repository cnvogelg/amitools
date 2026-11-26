"""Run the original AmigaOS 3.2.3 ``Rename`` command (see test/cli/README.md)."""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

RENAME_SHA1 = "294c26dfaea572a873f0f830b46b121f9d94142f"


def cli_rename_file_test(vrun, tmp_path):
    """``Rename <old> <new>`` moves a file."""
    skip_if_cmd_missing(vrun, "Rename", RENAME_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Rename", "work:ren.txt", "work:ren2.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    assert not (tmp_path / "ren.txt").exists()
    assert (tmp_path / "ren2.txt").read_text() == "rename me\n"


def cli_rename_overwrite_test(vrun, tmp_path):
    """``Rename`` replaces an existing destination."""
    skip_if_cmd_missing(vrun, "Rename", RENAME_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Rename", "work:ren.txt", "work:in.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    assert (tmp_path / "in.txt").read_text() == "rename me\n"


def cli_rename_missing_test(vrun, tmp_path):
    """A missing source file is reported with the DOS error name."""
    skip_if_cmd_missing(vrun, "Rename", RENAME_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "Rename",
        "work:missing.txt",
        "work:x.txt",
        expect_rc=20,
        vargs=work_vargs(tmp_path),
    )
    assert stdout == [
        "Can't rename work:missing.txt as work:x.txt because ERROR_OBJECT_NOT_FOUND"
    ]
    assert stderr == []
