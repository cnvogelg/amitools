"""Run the original AmigaOS 3.2.3 ``SetDate`` command (see test/cli/README.md).

``SetDate <file> DATE=<date>`` changes a file's date; without ``DATE`` it uses
the current time.  The change is observable on the host file's mtime.
"""

import datetime

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

SETDATE_SHA1 = "776441fae311743f9692e19c0c17b9a1126adcce"


def cli_setdate_explicit_test(vrun, tmp_path):
    """``SetDate <file> DATE=01-Jan-99`` sets the date to 1999-01-01."""
    skip_if_cmd_missing(vrun, "SetDate", SETDATE_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "SetDate", "work:in.txt", "DATE=01-Jan-99", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    mtime = datetime.datetime.fromtimestamp((tmp_path / "in.txt").stat().st_mtime)
    assert (mtime.year, mtime.month, mtime.day) == (1999, 1, 1)


def cli_setdate_now_test(vrun, tmp_path):
    """``SetDate <file>`` without ``DATE`` uses the current date."""
    skip_if_cmd_missing(vrun, "SetDate", SETDATE_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "SetDate", "work:in.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    mtime = datetime.datetime.fromtimestamp((tmp_path / "in.txt").stat().st_mtime)
    assert mtime.year == datetime.date.today().year
