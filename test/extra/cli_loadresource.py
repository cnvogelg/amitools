"""Run the original AmigaOS 3.2.3 ``LoadResource`` command (see test/cli/README.md).

``LoadResource NAME=<name>`` creates a resident helper process with
``CreateNewProc(NP_SegList=<its own loaded module>, ...)``, taking the module
from ``pr_CLI->cli_Module``.  vamos never fills that field with the running
command's seglist, so the command passes ``NP_SegList=0``, the helper task ends
at once and the parent blocks in ``WaitPort``/``Wait()`` (rc ``255``).  The test
asserts the intended behaviour and is ``xfail``.
"""

import pytest

from cli_util import run_cli_rc, skip_if_cmd_missing

LOADRESOURCE_SHA1 = "5ed2503fe7e33b3c5b46ba4e7e2a952794248223"


@pytest.mark.xfail(
    reason="LoadResource's helper gets NP_SegList=0 (no cli_Module) and the "
    "command waits forever",
    strict=True,
)
def cli_loadresource_test(vrun):
    """``LoadResource NAME=x`` loads the named resource."""
    skip_if_cmd_missing(vrun, "LoadResource", LOADRESOURCE_SHA1)
    stdout, stderr = run_cli_rc(vrun, "LoadResource", "NAME=x")
    assert stdout == []
    assert stderr == []
