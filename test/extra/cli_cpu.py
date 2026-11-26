"""Run the original AmigaOS 3.2.3 ``CPU`` command (see test/cli/README.md).

``CPU`` prints the emulated processor and its cache state.
"""

import re

from cli_util import run_cli_rc, skip_if_cmd_missing

CPU_SHA1 = "339d3c13eff9d98ee373668c863c56fb660476fb"

_SYSTEM = re.compile(r"System: 68000\s+\(INST: NoCache\)")


def cli_cpu_test(vrun):
    """``CPU`` prints the emulated processor."""
    skip_if_cmd_missing(vrun, "CPU", CPU_SHA1)
    stdout, stderr = run_cli_rc(vrun, "CPU")
    assert len(stdout) == 1
    assert _SYSTEM.fullmatch(stdout[0]), stdout
    assert stderr == []


def cli_cpu_nocache_test(vrun):
    """``CPU NOCACHE`` disables the instruction cache (already off by default)."""
    skip_if_cmd_missing(vrun, "CPU", CPU_SHA1)
    stdout, stderr = run_cli_rc(vrun, "CPU", "NOCACHE")
    assert len(stdout) == 1
    assert _SYSTEM.fullmatch(stdout[0]), stdout
    assert stderr == []
