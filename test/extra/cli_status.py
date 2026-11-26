"""Run the original AmigaOS 3.2.3 ``Status`` command (see test/cli/README.md).

``Status`` with no argument should list the running CLI processes.  vamos has
no CLI process table, so the list is empty and the command returns 20; the test
asserts the intended behaviour and is ``xfail``.

The numeric form is covered too: ``Status 1`` reports the (non-existent)
process, which is the expected result with an empty process table.
"""

import pytest

from cli_util import run_cli_rc, skip_if_cmd_missing

STATUS_SHA1 = "065742381ef0308f2d574835d74aa217dbe30735"


@pytest.mark.xfail(
    reason="Status has no CLI process table to list in vamos", strict=True
)
def cli_status_list_test(vrun):
    """``Status`` lists the running CLI processes."""
    skip_if_cmd_missing(vrun, "Status", STATUS_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Status")
    assert stdout
    assert stderr == []


def cli_status_missing_proc_test(vrun):
    """``Status 1`` reports that process 1 does not exist."""
    skip_if_cmd_missing(vrun, "Status", STATUS_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Status", "1", expect_rc=20)
    assert stdout == ["Process 1 does not exist"]
    assert stderr == []
