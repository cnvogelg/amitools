import pytest
from amitools.fd import read_lib_fd
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary
from amitools.vamos.libcore import LibImplScanner
from amitools.vamos.error import VamosInternalError


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
    # check funcs
    missing_funcs = res.get_missing_funcs()
    assert missing_funcs == {"Dummy": fd.get_func_by_name("Dummy")}
    missing_names = res.get_missing_func_names()
    assert missing_names == ["Dummy"]

    invalid_funcs = res.get_invalid_funcs()
    assert invalid_funcs == {"InvalidFunc": impl.InvalidFunc}
    invalid_names = res.get_invalid_func_names()
    assert invalid_names == ["InvalidFunc"]

    error_funcs = res.get_error_funcs()
    assert error_funcs == {
        "PrintHello": (fd.get_func_by_name("PrintHello"), impl.PrintHello)
    }
    error_names = res.get_error_func_names()
    assert error_names == ["PrintHello"]

    valid_funcs = res.get_valid_funcs()
    assert valid_funcs == {
        "PrintString": (fd.get_func_by_name("PrintString"), impl.PrintString),
        "Add": (fd.get_func_by_name("Add"), impl.Add),
        "Swap": (fd.get_func_by_name("Swap"), impl.Swap),
        "RaiseError": (fd.get_func_by_name("RaiseError"), impl.RaiseError),
        "ExecutePy": (fd.get_func_by_name("ExecutePy"), impl.ExecutePy)
    }
    valid_names = res.get_valid_func_names()
    assert valid_names == ["Add", "ExecutePy", "PrintString", "RaiseError", "Swap"]
