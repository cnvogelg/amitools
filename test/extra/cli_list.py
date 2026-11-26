"""Run the original AmigaOS 3.2.3 ``List`` command (see test/cli/README.md).

``List`` prints a directory's entries with their size, protection flags and
date, plus a summary line.  The date column is either ``Today`` or a real
date, so those lines are matched with a regex; the sizes and summaries are
deterministic because ``cli_util.make_work_tree`` writes fixed contents.
"""

import re

from cli_util import (
    assert_lines,
    make_work_tree,
    run_cli_rc,
    skip_if_cmd_missing,
    work_vargs,
)

LIST_SHA1 = "bae8df6ae7ea1ed00965f10ba01289b061179452"

# "Today HH:MM:SS" or "DD-Mon-YY HH:MM:SS"
_DATE = r"(?:Today|\d{2}-[A-Za-z]{3}-\d{2})\s+\d{2}:\d{2}:\d{2}"
_HEADER = re.compile(r'Directory "work:(?:sub)?" on \w+ \d{2}-[A-Za-z]{3}-\d{2}')


def _file(name, size, prot):
    return re.compile(r"%s\s+%d %s %s" % (re.escape(name), size, prot, _DATE))


def _dir(name, prot):
    return re.compile(r"%s\s+Dir %s %s" % (re.escape(name), prot, _DATE))


def cli_list_dir_test(vrun, tmp_path):
    """``List <dir>`` prints a header, the entries and a summary."""
    skip_if_cmd_missing(vrun, "List", LIST_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(vrun, "List", "work:", vargs=work_vargs(tmp_path))
    assert_lines(
        stdout,
        [
            _HEADER,
            _file("a.txt", 20, "----rw-d"),
            _file("b.txt", 8, "----rw-d"),
            _file("del.txt", 10, "----rw-d"),
            _file("in.txt", 12, "----rw-d"),
            _file("nested.txt", 7, "----rw-d"),
            _file("ren.txt", 10, "----rw-d"),
            _dir("sub", "----rwed"),
            "6 files - 67 bytes - 1 directory - 14 blocks used",
        ],
    )
    assert stderr == []


def cli_list_nohead_test(vrun, tmp_path):
    """``NOHEAD`` drops the header and the summary line."""
    skip_if_cmd_missing(vrun, "List", LIST_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "List", "work:", "NOHEAD", vargs=work_vargs(tmp_path)
    )
    assert_lines(
        stdout,
        [
            _file("a.txt", 20, "----rw-d"),
            _file("b.txt", 8, "----rw-d"),
            _file("del.txt", 10, "----rw-d"),
            _file("in.txt", 12, "----rw-d"),
            _file("nested.txt", 7, "----rw-d"),
            _file("ren.txt", 10, "----rw-d"),
            _dir("sub", "----rwed"),
        ],
    )
    assert stderr == []


def cli_list_pattern_test(vrun, tmp_path):
    """``P=<pattern>`` only lists the matching entries."""
    skip_if_cmd_missing(vrun, "List", LIST_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "List", "work:", "P=#?.txt", vargs=work_vargs(tmp_path)
    )
    assert_lines(
        stdout,
        [
            _HEADER,
            _file("a.txt", 20, "----rw-d"),
            _file("b.txt", 8, "----rw-d"),
            _file("del.txt", 10, "----rw-d"),
            _file("in.txt", 12, "----rw-d"),
            _file("nested.txt", 7, "----rw-d"),
            _file("ren.txt", 10, "----rw-d"),
            "6 files - 67 bytes - 12 blocks used",
        ],
    )
    assert stderr == []


def cli_list_subdir_test(vrun, tmp_path):
    """``List <subdir>`` lists a subdirectory."""
    skip_if_cmd_missing(vrun, "List", LIST_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(vrun, "List", "work:sub", vargs=work_vargs(tmp_path))
    assert_lines(
        stdout,
        [
            _HEADER,
            _file("deep.txt", 5, "----rw-d"),
            "1 file - 5 bytes - 2 blocks used",
        ],
    )
    assert stderr == []


def cli_list_all_test(vrun, tmp_path):
    """``ALL`` recurses into subdirectories and adds a TOTAL line."""
    skip_if_cmd_missing(vrun, "List", LIST_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "List", "work:", "ALL", vargs=work_vargs(tmp_path)
    )
    assert_lines(
        stdout,
        [
            _HEADER,
            _file("a.txt", 20, "----rw-d"),
            _file("b.txt", 8, "----rw-d"),
            _file("del.txt", 10, "----rw-d"),
            _file("in.txt", 12, "----rw-d"),
            _file("nested.txt", 7, "----rw-d"),
            _file("ren.txt", 10, "----rw-d"),
            _dir("sub", "----rwed"),
            "6 files - 67 bytes - 1 directory - 14 blocks used",
            "",
            _HEADER,
            _file("deep.txt", 5, "----rw-d"),
            "1 file - 5 bytes - 2 blocks used",
            "",
            "TOTAL: 7 files - 72 bytes - 1 directory - 16 blocks used",
        ],
    )
    assert stderr == []
