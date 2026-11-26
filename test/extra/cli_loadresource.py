"""Run the original AmigaOS 3.2.3 ``LoadResource`` command (see test/cli/README.md).

``LoadResource NAME=<name>`` should load a resident resource.  Under vamos the
task never terminates (it is left waiting) and the run returns 255; the test
asserts the intended behaviour and is ``xfail``.
"""

import pytest

from cli_util import run_cli_rc, skip_if_cmd_missing

LOADRESOURCE_SHA1 = "5ed2503fe7e33b3c5b46ba4e7e2a952794248223"


@pytest.mark.xfail(
    reason="LoadResource never terminates under vamos (task left waiting)",
    strict=True,
)
def cli_loadresource_test(vrun):
    """``LoadResource NAME=x`` loads the named resource."""
    skip_if_cmd_missing(vrun, "LoadResource", LOADRESOURCE_SHA1)
    stdout, stderr = run_cli_rc(vrun, "LoadResource", "NAME=x")
    assert stdout == []
    assert stderr == []
