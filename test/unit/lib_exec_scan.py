"""exec.library scan guard (EXEC.md step 1n / Stage 2).

Reports the implemented/missing split for ``exec.library`` after the topic
mixin refactor and the Stage 2 implementation. It guards the structural
contract: every fd function that has a method must match the fd signature, the
Stage 2 set of implemented functions must not shrink, and the only functions
left unimplemented are the private ``execPrivate*`` slots.
"""

from amitools.fd import read_lib_fd
from amitools.vamos.lib.ExecLibrary import ExecLibrary
from amitools.vamos.libcore.impl import LibImplScanner

# Stage 2: every public LVO is implemented (82 Stage 1 + 40 Stage 2).
# This set must never shrink.
STAGE2_VALID = 122


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
    # the implemented set must not shrink
    assert scan.get_num_valid_funcs() >= STAGE2_VALID
    # the private execPrivate* slots stay stubs; nothing public is missing
    missing = scan.get_missing_func_names()
    assert all(name.startswith("execPrivate") for name in missing)
