"""dos.library is complete: every fd function is bound but the placeholders.

``dosPrivate1/2/3/7`` are reserved holes in the FD and stay unimplemented.
Everything else must be a valid implementation (no ``*args``/defaults) so the
scanner maps each function to its fd registers.
"""

from amitools.fd import read_lib_fd
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libcore.impl import LibImplScanner


def lib_dos_complete_test():
    fd = read_lib_fd("dos.library", add_std_calls=False)
    scan = LibImplScanner().scan("dos.library", DosLibrary(), fd)

    assert scan.get_error_func_names() == []
    assert scan.get_invalid_func_names() == []
    assert scan.get_missing_func_names() == [
        "dosPrivate1",
        "dosPrivate2",
        "dosPrivate3",
        "dosPrivate7",
    ]
    assert scan.get_num_valid_funcs() == len(fd.get_funcs()) - 4
