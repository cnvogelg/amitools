"""Run the original AmigaOS 3.2.3 ``SetFont`` command (see test/cli/README.md).

``SetFont NAME SIZE`` selects a font for the console.  ``vamos`` accepts the
built-in ``topaz.font`` and reports a missing font file for an unknown name.
The missing-argument case is covered by the ``cli_readargs`` smoke test.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

SETFONT_SHA1 = "895c3945eeee1d259c55775d4527c8df299be70d"


def cli_setfont_test(vrun):
    """``SetFont topaz.font 8`` selects the built-in font."""
    skip_if_cmd_missing(vrun, "SetFont", SETFONT_SHA1)
    stdout, stderr = run_cli_rc(vrun, "SetFont", "topaz.font", "8")
    assert stdout == []
    assert stderr == []


def cli_setfont_missing_test(vrun):
    """An unknown font file is reported as missing."""
    skip_if_cmd_missing(vrun, "SetFont", SETFONT_SHA1)
    stdout, stderr = run_cli_rc(vrun, "SetFont", "nosuch.font", "8", expect_rc=20)
    assert stdout == ["ERROR_OBJECT_NOT_FOUND"]
    assert stderr == []
