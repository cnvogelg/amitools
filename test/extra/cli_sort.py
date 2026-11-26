"""Run the original AmigaOS 3.2.3 ``Sort`` command (see test/cli/README.md).

``Sort`` sorts the lines of a file into another file.
"""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

SORT_SHA1 = "a7692005073b8b59290dbad6b2905c9a379d68e3"


def cli_sort_file_test(vrun, tmp_path):
    """``Sort <in> <out>`` sorts the input lines into the output file."""
    skip_if_cmd_missing(vrun, "Sort", SORT_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Sort", "work:a.txt", "work:sorted.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    assert (tmp_path / "sorted.txt").read_text() == "apple\nbanana\ncherry\n"


def cli_sort_from_to_test(vrun, tmp_path):
    """``Sort FROM <in> TO <out>`` is the long form of the same command."""
    skip_if_cmd_missing(vrun, "Sort", SORT_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "Sort",
        "FROM",
        "work:a.txt",
        "TO",
        "work:sorted.txt",
        vargs=work_vargs(tmp_path),
    )
    assert stdout == []
    assert stderr == []
    assert (tmp_path / "sorted.txt").read_text() == "apple\nbanana\ncherry\n"


def cli_sort_missing_test(vrun, tmp_path):
    """A missing input file is reported."""
    skip_if_cmd_missing(vrun, "Sort", SORT_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "Sort",
        "work:missing.txt",
        "work:sorted.txt",
        expect_rc=10,
        vargs=work_vargs(tmp_path),
    )
    assert stdout == [
        "ERROR_OBJECT_NOT_FOUND",
        'Cannot open input file "work:missing.txt": ERROR_OBJECT_NOT_FOUND',
    ]
    assert stderr == []
