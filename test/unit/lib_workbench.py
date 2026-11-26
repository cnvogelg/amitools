from types import SimpleNamespace

from amitools.fd import read_lib_fd
from amitools.vamos.lib.WorkbenchLibrary import WorkbenchLibrary
from amitools.vamos.libcore import LibImplScanner, LibImplFuncTag


def lib_workbench_wbinfo_test():
    """``WBInfo`` reports success without touching any register args."""
    lib = WorkbenchLibrary()
    ctx = SimpleNamespace()
    assert lib.WBInfo(ctx, 0x1234, 0x5678, 0) == 1


def lib_workbench_scan_test():
    """The implementation matches the FD entry for ``WBInfo`` (LVO -90)."""
    name = "workbench.library"
    fd = read_lib_fd(name)
    impl = WorkbenchLibrary()
    scanner = LibImplScanner()
    res = scanner.scan(name, impl, fd)
    assert res.get_valid_func_names() == ["WBInfo"]
    assert res.get_num_valid_funcs() == 1
    wbinfo = res.get_func_by_name("WBInfo")
    assert wbinfo.tag == LibImplFuncTag.TAG_VALID
    assert wbinfo.fd_func.get_bias() == 90
    # the extra args are read from a0/a1/a2
    assert [arg.reg for arg in wbinfo.extra_args] == [8, 9, 10]
