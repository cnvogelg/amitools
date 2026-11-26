"""Run the original AmigaOS 3.2.3 ``Avail`` command (see test/cli/README.md).

``Avail`` prints the free memory per memory type.  The sizes depend on the
``vamos`` configuration, so the numeric columns are matched with a regex.
"""

import re

from cli_util import run_cli_rc, skip_if_cmd_missing

AVAIL_SHA1 = "e2947b8456070341dde817298ed917d79dc22552"

_HEADER = "Type  Available    In-Use   Maximum   Largest"
_ROW = re.compile(r"(?:chip|fast|total)\s+\d+\s+\d+\s+\d+\s+\d+")


def cli_avail_table_test(vrun):
    """``Avail`` prints a header and one row per memory type."""
    skip_if_cmd_missing(vrun, "Avail", AVAIL_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Avail")
    assert len(stdout) == 4
    assert stdout[0] == _HEADER
    for row, name in zip(stdout[1:], ("chip", "fast", "total")):
        assert row.startswith(name)
        assert _ROW.fullmatch(row), row
    assert stderr == []


def cli_avail_total_test(vrun):
    """``Avail TOTAL`` prints only the total number of free bytes."""
    skip_if_cmd_missing(vrun, "Avail", AVAIL_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Avail", "TOTAL")
    assert len(stdout) == 1
    assert stdout[0].isdigit(), stdout
    assert stderr == []
