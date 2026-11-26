"""Run the original AmigaOS 3.2.3 ``Eval`` command (see test/cli/README.md).

``Eval`` evaluates an arithmetic expression and prints the result.  Only the
arithmetic subset works; comparisons are rejected by the parser.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

EVAL_SHA1 = "648fe7e4262b05716af6ff32ab4cb5aef38c93b7"


def _eval(vrun, expr, expected):
    skip_if_cmd_missing(vrun, "Eval", EVAL_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Eval", expr)
    assert stdout == [expected], "%r -> %r" % (expr, stdout)
    assert stderr == []


def cli_eval_add_test(vrun):
    """``Eval 2+3`` adds two decimal numbers."""
    _eval(vrun, "2+3", "5")


def cli_eval_hex_test(vrun):
    """``Eval`` accepts hexadecimal literals."""
    _eval(vrun, "0x10+1", "17")


def cli_eval_not_test(vrun):
    """``Eval ~5`` is a 32 bit complement (unsigned result)."""
    _eval(vrun, "~5", "4294967290")


def cli_eval_and_test(vrun):
    """``Eval 6&3`` is a bitwise and."""
    _eval(vrun, "6&3", "2")


def cli_eval_div_test(vrun):
    """``Eval 6/2`` divides."""
    _eval(vrun, "6/2", "3")
