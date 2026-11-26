"""Run the original AmigaOS 3.2.3 ``Date`` command (see test/cli/README.md).

``Date`` prints the current date; with ``TO=<file>`` it writes it to a file
instead.  The actual value depends on the host clock, so it is matched with a
regex.
"""

import re

from cli_util import run_cli_rc, skip_if_cmd_missing, work_vargs

DATE_SHA1 = "28ae411c9fcada25598839710b3b566a6a726f0f"

# "Thursday 26-Nov-26 22:01:42"
_DATE = re.compile(r"\w+ \d{2}-[A-Za-z]{3}-\d{2} \d{2}:\d{2}:\d{2}")


def cli_date_now_test(vrun):
    """``Date`` prints the current date and time."""
    skip_if_cmd_missing(vrun, "Date", DATE_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Date")
    assert len(stdout) == 1
    assert _DATE.fullmatch(stdout[0]), stdout
    assert stderr == []


def cli_date_to_file_test(vrun, tmp_path):
    """``Date TO=<file>`` writes the date to a file instead of stdout."""
    skip_if_cmd_missing(vrun, "Date", DATE_SHA1)
    stdout, stderr = run_cli_rc(
        vrun, "Date", "TO=work:d.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    text = (tmp_path / "d.txt").read_text().strip()
    assert _DATE.fullmatch(text), text
