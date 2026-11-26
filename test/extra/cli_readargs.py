"""Cross-cutting ``ReadArgs`` smoke test (see test/cli/README.md).

Every command with a required argument must reject a missing one with
``ERROR_REQUIRED_ARG_MISSING`` (return code 20).  ``Install`` appends its own
failure line, and ``Group``/``Owner`` prefix the message with the command name.

``RequestFile`` has no required argument (it opens a requester) and returns 5
without a message, so it is excluded.
"""

import pytest

from cli_util import run_cli_rc, skip_if_cmd_missing

_MISSING = "ERROR_REQUIRED_ARG_MISSING"

# (command, sha1, expected stdout lines)
CASES = [
    ("AddBuffers", "b8bae93dc109c0bc18f87b372361cf44eb8046c2", [_MISSING]),
    ("Break", "04c35975cbf7a0790a90bd7d7927c2cdbdb8d233", [_MISSING]),
    ("ChangeTaskPri", "cfde61b5d9a94d6b77238c8ea9498a8a2826239b", [_MISSING]),
    ("DiskChange", "650836abbddba51990ccb58cf847473c3ff85c99", [_MISSING]),
    ("MakeLink", "f1d8d6e57c3942cc61a6603038084abc1d3652e1", [_MISSING]),
    ("RequestChoice", "bf4c7f185f4c28bf84ee7872ac32b7de7423e3a5", [_MISSING]),
    ("SetFont", "895c3945eeee1d259c55775d4527c8df299be70d", [_MISSING]),
    ("SetKeyboard", "31884318765220bb3c3b79f84f946ade58b0ee70", [_MISSING]),
    (
        "Install",
        "5af5975ef92ec650bf6648cce9697a9a51d5fe42",
        [_MISSING, "Install failed"],
    ),
    ("CopyTooltypes", "09dbf313267f2d4983c0abf381069e289508d4c6", [_MISSING]),
    ("Group", "6451090722636d3d9e69a975b8c8d1455cc7b0b0", ["GROUP: " + _MISSING]),
    ("Owner", "54bafce8ee40e8bafa6dd3f11215cd1063745ecf", ["OWNER: " + _MISSING]),
]


@pytest.mark.parametrize("name,sha1,expected", CASES, ids=[case[0] for case in CASES])
def cli_readargs_missing_test(vrun, name, sha1, expected):
    """A command with a required argument rejects a missing one."""
    skip_if_cmd_missing(vrun, name, sha1)
    stdout, stderr = run_cli_rc(vrun, name, expect_rc=20)
    assert stdout == expected
    assert stderr == []
