"""Run the original AmigaOS 3.2.3 ``Type`` command (see test/cli/README.md).

``Type`` copies one or more files to the current output.  It is a plain
``proc``-mode command, so the run stays in-process unless ``--run-subproc``
is given.
"""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

TYPE_SHA1 = "39ccf36f48f13772f0744bc98c42ee01e7a13984"


def cli_type_file_test(vrun, tmp_path):
    """``Type <file>`` prints the file's contents."""
    skip_if_cmd_missing(vrun, "Type", TYPE_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(vrun, "Type", "work:in.txt", vargs=work_vargs(tmp_path))
    assert stdout == ["hello", "world"]
    assert stderr == []


def cli_type_multiple_test(vrun, tmp_path):
    """``Type`` accepts several files (``FILE/A``) and concatenates them."""
    skip_if_cmd_missing(vrun, "Type", TYPE_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Type", "work:a.txt", "work:b.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == ["banana", "apple", "cherry", "dog", "cat"]
    assert stderr == []


def cli_type_missing_test(vrun, tmp_path):
    """A missing file is reported with the AmigaDOS error name."""
    skip_if_cmd_missing(vrun, "Type", TYPE_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Type", "work:missing.txt", expect_rc=10, vargs=work_vargs(tmp_path)
    )
    assert stdout == ["TYPE can't open work:missing.txt", "ERROR_OBJECT_NOT_FOUND"]
    assert stderr == []
