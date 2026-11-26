"""Run the original AmigaOS 3.2.3 ``Which`` command (see test/cli/README.md).

``Which <command>`` should print the path of an executable.  Under vamos it
returns 5 and prints nothing, so the test is ``xfail``.
"""

import pytest

from cli_util import run_cli_rc, skip_if_cmd_missing

WHICH_SHA1 = "408453c504fdcad87cf9b827ab672effe50d21b6"


@pytest.mark.xfail(
    reason="Which returns 5 without printing the command path", strict=True
)
def cli_which_test(vrun):
    """``Which Type`` prints the location of ``Type``."""
    skip_if_cmd_missing(vrun, "Which", WHICH_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Which", "Type")
    assert any("Type" in line for line in stdout)
    assert stderr == []
