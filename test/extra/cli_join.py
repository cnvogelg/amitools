"""Run the original AmigaOS 3.2.3 ``Join`` command (see test/cli/README.md).

``Join`` concatenates the given files into one output file.
"""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

JOIN_SHA1 = "3b6b1fb2ec0dace4754d09a0079309248634323b"


def cli_join_file_test(vrun, tmp_path):
    """``Join <a> <b> AS <out>`` concatenates two files."""
    skip_if_cmd_missing(vrun, "Join", JOIN_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "Join",
        "work:a.txt",
        "work:b.txt",
        "as",
        "work:joined.txt",
        vargs=work_vargs(tmp_path),
    )
    assert stdout == []
    assert stderr == []
    assert (tmp_path / "joined.txt").read_text() == "banana\napple\ncherry\ndog\ncat\n"


def cli_join_multiple_test(vrun, tmp_path):
    """``Join`` accepts more than two input files (``FILE/A``)."""
    skip_if_cmd_missing(vrun, "Join", JOIN_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "Join",
        "work:a.txt",
        "work:b.txt",
        "work:in.txt",
        "as",
        "work:joined.txt",
        vargs=work_vargs(tmp_path),
    )
    assert stdout == []
    assert stderr == []
    assert (
        tmp_path / "joined.txt"
    ).read_text() == "banana\napple\ncherry\ndog\ncat\nhello\nworld\n"


def cli_join_missing_test(vrun, tmp_path):
    """A missing input file is reported."""
    skip_if_cmd_missing(vrun, "Join", JOIN_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "Join",
        "work:missing.txt",
        "work:b.txt",
        "as",
        "work:joined.txt",
        expect_rc=20,
        vargs=work_vargs(tmp_path),
    )
    assert stdout == ["Can't open work:missing.txt"]
    assert stderr == []
