"""Run the original AmigaOS 3.2.3 ``Which`` command (see test/cli/README.md).

``Which <command>`` prints the path of an executable.  It only considers files
whose AmigaDOS protection has the execute bit set, so the fixture command is
marked executable first (see ``extract-cli.py``); the real ``C:`` drawer is
executable too.
"""

from cli_util import ensure_cmd_executable, run_cli_rc, skip_if_cmd_missing

WHICH_SHA1 = "408453c504fdcad87cf9b827ab672effe50d21b6"


def cli_which_test(vrun):
    """``Which Type`` prints the location of ``Type``."""
    skip_if_cmd_missing(vrun, "Which", WHICH_SHA1)
    ensure_cmd_executable("Type")
    stdout, stderr = run_cli_rc(vrun, "Which", "Type")
    assert stdout == ["cli:C/Type"]
    assert stderr == []


def cli_which_missing_test(vrun):
    """``Which`` sets the condition flag (rc 5) and prints nothing for a
    command it cannot find."""
    skip_if_cmd_missing(vrun, "Which", WHICH_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Which", "NosuchCommand", expect_rc=5)
    assert stdout == []
    assert stderr == []
