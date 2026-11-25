"""Run the original AmigaOS ARexx environment (rexxsyslib + RexxMast + RX).

The ARexx binaries are copyrighted AmigaOS files and are never committed; the
tests skip unless the fixtures were extracted into ``test/arexx`` (see
``test/arexx/README.md``).
"""

REXXSYSLIB_SHA1 = "54982a5e9919097050c3fe56cb319e20763e6326"
REXXMAST_SHA1 = "c5ff779e18ea2d15275f62ccab5746b2d66d2d5d"
RX_SHA1 = "cb62bb549d954f889b46faf00e8655975eea3a89"

# The ARexx runtime: the library via LIBS:, the REXX: assign points at S:, and
# the Rexxc commands are on the command path.
AREX_ARGS = [
    "-alibs:arexx:Libs",
    "-a",
    "REXX:arexx:S",
    "-p",
    "arexx:System,arexx:Rexxc",
]

# rexxsyslib prints its banner during init. The console handler emits UTF-8, so
# the (c) sign shows up as its two UTF-8 bytes when stdout is read as latin-1.
COPYRIGHT = "Copyright \u00a9 1987 by William S. Hawes".encode("utf-8").decode(
    "latin-1"
)
BANNER = [
    "ARexx Version 1.15",
    COPYRIGHT,
    "All Rights Reserved",
]


def _check_arexx(vrun):
    # add_volume_or_skip appends to the shared vamos args; keep it idempotent
    if "-Varexx:arexx" not in vrun.vamos_args:
        vrun.add_volume_or_skip("arexx", "arexx")
    vrun.skip_if_prog_not_available("arexx/Libs/rexxsyslib.library", REXXSYSLIB_SHA1)
    vrun.skip_if_prog_not_available("arexx/System/RexxMast", REXXMAST_SHA1)
    vrun.skip_if_prog_not_available("arexx/Rexxc/RX", RX_SHA1)


def arexx_rx_script_test(vrun):
    """RX finds/launches RexxMast and runs a REXX script to completion"""
    _check_arexx(vrun)
    retcode, stdout, stderr = vrun.run_prog(
        "arexx:Rexxc/RX",
        "SCRIPT=hello.rexx",
        vargs=list(AREX_ARGS),
    )
    assert stdout == BANNER + ["Hello from ARexx", "1+2= 3"]
    assert stderr == []
    assert retcode == 0


def arexx_rx_missing_script_test(vrun):
    """a script that cannot be found reports 'Program not found' (rc 5)"""
    _check_arexx(vrun)
    retcode, stdout, stderr = vrun.run_prog(
        "arexx:Rexxc/RX",
        "SCRIPT=does-not-exist.rexx",
        vargs=list(AREX_ARGS),
    )
    # RX reports the ARexx error code and the interpreter's error text on a
    # single line: "Command returned <rc>/<index>: <error text>"
    assert stdout[: len(BANNER)] == BANNER
    assert "Command returned 5/1: Program not found" in stdout
    assert retcode == 5
