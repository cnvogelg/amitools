import pytest
from amitools.fd import read_lib_fd
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary
from amitools.vamos.libcore import LibImplScanner, LibImplScan, LibImplFuncArg
from amitools.vamos.error import VamosInternalError
from amitools.vamos.machine.regs import *


def libcore_impl_scan_checked_vamos_test():
    name = "vamostest.library"
    fd = read_lib_fd(name)
    impl = VamosTestLibrary()
    scanner = LibImplScanner()
    with pytest.raises(VamosInternalError):
        scanner.scan_checked(name, impl, fd)


def libcore_impl_scan_vamos_test():
    name = "vamostest.library"
    fd = read_lib_fd(name)
    impl = VamosTestLibrary()
    # inject error func

    def PrintHello(self, ctx, wrong):
        pass

    impl.PrintHello = PrintHello.__get__(impl, impl.__class__)
    # scan impl
    scanner = LibImplScanner()
    res = scanner.scan(name, impl, fd)
    assert res.get_name() == name
    assert res.get_impl() == impl
    assert res.get_fd() == fd
    assert res.get_num_valid_funcs() == 5
    assert res.get_num_missing_funcs() == 1
    assert res.get_num_error_funcs() == 1
    assert res.get_num_invalid_funcs() == 1

    # missing func
    missing_funcs = res.get_missing_funcs()
    missing_func = res.get_func_by_name("Dummy")
    assert missing_funcs == {"Dummy": missing_func}
    assert missing_func.name == "Dummy"
    assert missing_func.fd_func == fd.get_func_by_name("Dummy")
    assert missing_func.method is None
    assert missing_func.tag == LibImplScan.TAG_MISSING
    assert missing_funcs == {"Dummy": missing_func}
    missing_names = res.get_missing_func_names()
    assert missing_names == ["Dummy"]

    # invalid func
    invalid_funcs = res.get_invalid_funcs()
    invalid_func = res.get_func_by_name("InvalidFunc")
    assert invalid_funcs == {"InvalidFunc": invalid_func}
    assert invalid_func.name == "InvalidFunc"
    assert invalid_func.fd_func == fd.get_func_by_name("InvalidFunc")
    assert invalid_func.method == impl.InvalidFunc
    assert invalid_func.tag == LibImplScan.TAG_INVALID
    invalid_names = res.get_invalid_func_names()
    assert invalid_names == ["InvalidFunc"]

    # error func
    error_funcs = res.get_error_funcs()
    error_func = res.get_func_by_name("PrintHello")
    assert error_func.name == "PrintHello"
    assert error_func.fd_func == fd.get_func_by_name("PrintHello")
    assert error_func.method == impl.PrintHello
    assert error_func.tag == LibImplScan.TAG_ERROR
    assert error_funcs == {"PrintHello": error_func}
    error_names = res.get_error_func_names()
    assert error_names == ["PrintHello"]

    # valid funcs
    valid_funcs = res.get_valid_funcs()
    assert valid_funcs == {
        "PrintString": res.get_func_by_name("PrintString"),
        "Add": res.get_func_by_name("Add"),
        "Swap": res.get_func_by_name("Swap"),
        "RaiseError": res.get_func_by_name("RaiseError"),
        "ExecutePy": res.get_func_by_name("ExecutePy"),
    }
    valid_names = res.get_valid_func_names()
    assert valid_names == ["Add", "ExecutePy", "PrintString", "RaiseError", "Swap"]
    valid_func = res.get_func_by_name("ExecutePy")
    assert valid_func.name == "ExecutePy"
    assert valid_func.fd_func == fd.get_func_by_name("ExecutePy")
    assert valid_func.method == impl.ExecutePy
    assert valid_func.tag == LibImplScan.TAG_VALID


def libcore_impl_scan_vamos_extra_args_test():
    name = "vamostest.library"
    fd = read_lib_fd(name)
    impl = VamosTestLibrary()

    # setup test function with annotated args
    # also test name replacement with _ if it collides with Python
    def PrintString(self, ctx, str_: str):
        pass

    impl.PrintString = PrintString.__get__(impl, impl.__class__)

    # scan impl
    scanner = LibImplScanner()
    res = scanner.scan(name, impl, fd)

    # check valid funcs
    valid_func = res.get_func_by_name("ExecutePy")
    assert valid_func.name == "ExecutePy"
    assert valid_func.fd_func == fd.get_func_by_name("ExecutePy")
    assert valid_func.method == impl.ExecutePy
    assert valid_func.tag == LibImplScan.TAG_VALID
    assert valid_func.extra_args == [
        LibImplFuncArg("argc", REG_D0, int),
        LibImplFuncArg("argv", REG_A0, int),
    ]

    valid_func = res.get_func_by_name("PrintString")
    assert valid_func.name == "PrintString"
    assert valid_func.fd_func == fd.get_func_by_name("PrintString")
    assert valid_func.method == impl.PrintString
    assert valid_func.tag == LibImplScan.TAG_VALID
    assert valid_func.extra_args == [
        LibImplFuncArg("str", REG_A0, str),
    ]
