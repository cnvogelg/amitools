"""Run the original AmigaOS 3.2.3 ``Search`` command (see test/cli/README.md).

``Search <dir> <string>`` prints the lines of the files in ``dir`` that contain
``string``.  ``Search`` builds an upper-case pattern and hands it straight to
``dos.library/MatchPatternNoCase``; the matcher used to fold only the text, so
the upper-case pattern never matched and the command returned ``5``.  The
matcher now folds both sides (see ``test/unit/lib_dos_pattern.py``).
"""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

SEARCH_SHA1 = "72a6bbd06f4acca369ad01da2daadc5b940d744f"


def cli_search_dir_test(vrun, tmp_path):
    """``Search work: hello`` finds ``hello`` in ``work:in.txt``."""
    skip_if_cmd_missing(vrun, "Search", SEARCH_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Search", "work:", "hello", vargs=work_vargs(tmp_path)
    )
    assert "     1 hello" in stdout
    assert stderr == []


def cli_search_file_test(vrun, tmp_path):
    """``Search <file> <string>`` searches a single file."""
    skip_if_cmd_missing(vrun, "Search", SEARCH_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Search", "work:in.txt", "world", vargs=work_vargs(tmp_path)
    )
    assert stdout == ["     2 world"]
    assert stderr == []


def cli_search_nomatch_test(vrun, tmp_path):
    """A string that does not occur returns ``5`` without a match line."""
    skip_if_cmd_missing(vrun, "Search", SEARCH_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Search", "work:in.txt", "zzz", expect_rc=5, vargs=work_vargs(tmp_path)
    )
    assert all("zzz" not in line for line in stdout)
    assert stderr == []
