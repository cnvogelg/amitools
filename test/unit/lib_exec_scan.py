"""exec.library scan guard (EXEC.md step 1n).

Reports the implemented/missing split for ``exec.library`` after the topic
mixin refactor. It does not fail while public LVOs are still missing (Stage 2
implements them); it only guards the structural contract: every fd function
that has a method must match the fd signature, and the Stage 1 set of 82
functions must not shrink.
"""

from amitools.fd import read_lib_fd
from amitools.vamos.lib.ExecLibrary import ExecLibrary
from amitools.vamos.libcore.impl import LibImplScanner

# Stage 1 refactor: the 82 functions present in the original monolith.
# Stage 2 grows this set; it must never shrink.
STAGE1_VALID = 82


def _scan():
    fd = read_lib_fd("exec.library")
    return fd, LibImplScanner().scan("exec.library", ExecLibrary(), fd)


def lib_exec_scan_report_test():
    _fd, scan = _scan()
    print(
        "exec.library: %d valid, %d missing, %d invalid, %d error"
        % (
            scan.get_num_valid_funcs(),
            scan.get_num_missing_funcs(),
            scan.get_num_invalid_funcs(),
            scan.get_num_error_funcs(),
        )
    )
    # a method that does not match its fd entry is a real bug
    assert scan.get_num_invalid_funcs() == 0
    assert scan.get_num_error_funcs() == 0
    # the refactored set must not shrink
    assert scan.get_num_valid_funcs() >= STAGE1_VALID
