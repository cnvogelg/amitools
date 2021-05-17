import logging
import pytest

from amitools.vamos.libcore import LibStubGen, LibCtx, LibImplScanner
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary
from amitools.vamos.machine import MockMachine
from amitools.vamos.libcore import LibProfileData
from amitools.fd import read_lib_fd
from amitools.vamos.machine.regs import *


def _check_stub(stub):
    # check func tab
    func_tab = stub.get_func_tab()
    for f in func_tab:
        assert f is not None


def _check_profile(fd, profile):
    print_hello_func = fd.get_func_by_name("PrintHello")
    dummy_func = fd.get_func_by_name("Dummy")
    print_hello_prof = profile.get_func_by_index(print_hello_func.get_index())
    dummy_func_prof = profile.get_func_by_index(dummy_func.get_index())
    assert print_hello_prof.get_num_calls() == 1
    assert dummy_func_prof.get_num_calls() == 1
    profile.dump("bla")


def _check_log(caplog):
    assert caplog.record_tuples == [
        ("valid", logging.INFO, "{ CALL:   30 PrintHello(  ) from PC=000000"),
        ("valid", logging.INFO, "} CALL: -> d0=00000000"),
        (
            "missing",
            logging.WARN,
            "? CALL:   54 Dummy( a[d0]=00000000, b[d1]=00000000 ) from PC=000000 -> d0=0 (default)",
        ),
        (
            "valid",
            logging.INFO,
            "{ CALL:   48 Swap( a[d0]=00000000, b[d1]=00000000 ) from PC=000000",
        ),
        ("valid", logging.INFO, "} CALL: -> d0=00000000, d1=00000000"),
        (
            "valid",
            logging.INFO,
            "{ CALL:   36 PrintString( str[a0]=00000010 ) from PC=000000",
        ),
        ("valid", logging.INFO, "} CALL: -> d0=00000000"),
    ]


def _check_log_fake(caplog):
    assert caplog.record_tuples == [
        (
            "missing",
            logging.WARN,
            "? CALL:   30 PrintHello(  ) from PC=000000 -> d0=0 (default)",
        ),
        (
            "missing",
            logging.WARN,
            "? CALL:   54 Dummy( a[d0]=00000000, b[d1]=00000000 ) from PC=000000 -> d0=0 (default)",
        ),
        (
            "missing",
            logging.WARN,
            "? CALL:   48 Swap( a[d0]=00000000, b[d1]=00000000 ) from PC=000000 -> d0=0 (default)",
        ),
        (
            "missing",
            logging.WARN,
            "? CALL:   36 PrintString( str[a0]=00000010 ) from PC=000000 -> d0=0 "
            "(default)",
        ),
    ]


def _create_ctx():
    machine = MockMachine()
    # prepare PrintString()
    machine.mem.w_cstr(0x10, "hello, world!")
    machine.cpu.w_reg(REG_A0, 0x10)
    return LibCtx(machine)


def _create_scan():
    name = "vamostest.library"
    impl = VamosTestLibrary()
    fd = read_lib_fd(name)
    scanner = LibImplScanner()
    return scanner.scan(name, impl, fd, True)


def libcore_stub_gen_base_test(capsys):
    scan = _create_scan()
    ctx = _create_ctx()
    # create stub
    gen = LibStubGen()
    stub = gen.gen_stub(scan, ctx)
    _check_stub(stub)
    # call func
    stub.PrintHello()
    cap = capsys.readouterr()
    assert cap.out.strip() == "VamosTest: PrintHello()"
    stub.Dummy()
    # check arg transfer
    ctx.cpu.w_reg(REG_D0, 21)
    ctx.cpu.w_reg(REG_D1, 10)
    stub.Swap()
    assert ctx.cpu.r_reg(REG_D0) == 10
    assert ctx.cpu.r_reg(REG_D1) == 21
    # check return
    stub.Add()
    assert ctx.cpu.r_reg(REG_D0) == 31
    stub.PrintString()
    cap = capsys.readouterr()
    assert cap.out.strip() == "VamosTest: PrintString('hello, world!')"


def libcore_stub_gen_profile_test():
    scan = _create_scan()
    ctx = _create_ctx()
    profile = LibProfileData(scan.get_fd())
    # create stub
    gen = LibStubGen()
    stub = gen.gen_stub(scan, ctx, profile)
    _check_stub(stub)
    # call func
    stub.PrintHello()
    stub.Dummy()
    stub.Swap()
    stub.PrintString()
    _check_profile(scan.get_fd(), profile)


def libcore_stub_gen_log_test(caplog):
    caplog.set_level(logging.INFO)
    scan = _create_scan()
    ctx = _create_ctx()
    log_missing = logging.getLogger("missing")
    log_valid = logging.getLogger("valid")
    # create stub
    gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)
    stub = gen.gen_stub(scan, ctx)
    _check_stub(stub)
    # call func
    stub.PrintHello()
    stub.Dummy()
    stub.Swap()
    stub.PrintString()
    _check_log(caplog)


def libcore_stub_gen_log_profile_test(caplog):
    caplog.set_level(logging.INFO)
    scan = _create_scan()
    ctx = _create_ctx()
    log_missing = logging.getLogger("missing")
    log_valid = logging.getLogger("valid")
    profile = LibProfileData(scan.get_fd())
    # create stub
    gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)
    stub = gen.gen_stub(scan, ctx, profile)
    _check_stub(stub)
    # call func
    stub.PrintHello()
    stub.Dummy()
    stub.Swap()
    stub.PrintString()
    _check_log(caplog)
    _check_profile(scan.get_fd(), profile)


def libcore_stub_gen_exc_default_test():
    scan = _create_scan()
    ctx = _create_ctx()
    # create stub
    gen = LibStubGen()
    stub = gen.gen_stub(scan, ctx)
    _check_stub(stub)
    # call func
    ctx.cpu.w_reg(REG_A0, 0x20)
    ctx.mem.w_cstr(0x20, "RuntimeError")
    with pytest.raises(RuntimeError):
        stub.RaiseError()


def libcore_stub_gen_multi_arg_test(caplog):
    caplog.set_level(logging.INFO)
    scan = _create_scan()
    ctx = _create_ctx()
    log_missing = logging.getLogger("missing")
    log_valid = logging.getLogger("valid")
    profile = LibProfileData(scan.get_fd())
    # create stub
    gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)
    stub = gen.gen_stub(scan, ctx, profile)
    _check_stub(stub)
    # call func
    stub.PrintHello(1, 2, a=3)
    stub.Dummy(3, b="hello")
    stub.Swap("hugo", None, c=3)
    stub.PrintString("a", b=4, c=5)
    _check_log(caplog)
    _check_profile(scan.get_fd(), profile)


def libcore_stub_gen_fake_base_test():
    name = "vamostest.library"
    fd = read_lib_fd(name)
    ctx = _create_ctx()
    # create stub
    gen = LibStubGen()
    stub = gen.gen_fake_stub(name, fd, ctx)
    _check_stub(stub)
    # call func
    stub.PrintHello()
    stub.Dummy()
    stub.Swap()
    stub.PrintString()


def libcore_stub_gen_fake_profile_test():
    name = "vamostest.library"
    fd = read_lib_fd(name)
    ctx = _create_ctx()
    profile = LibProfileData(fd)
    # create stub
    gen = LibStubGen()
    stub = gen.gen_fake_stub(name, fd, ctx, profile)
    _check_stub(stub)
    # call func
    stub.PrintHello()
    stub.Dummy()
    stub.Swap()
    stub.PrintString()
    _check_profile(fd, profile)


def libcore_stub_gen_fake_log_test(caplog):
    caplog.set_level(logging.INFO)
    name = "vamostest.library"
    fd = read_lib_fd(name)
    ctx = _create_ctx()
    log_missing = logging.getLogger("missing")
    log_valid = logging.getLogger("valid")
    # create stub
    gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)
    stub = gen.gen_fake_stub(name, fd, ctx)
    _check_stub(stub)
    # call func
    stub.PrintHello()
    stub.Dummy()
    stub.Swap()
    stub.PrintString()
    _check_log_fake(caplog)


def libcore_stub_gen_fake_log_profile_test(caplog):
    caplog.set_level(logging.INFO)
    name = "vamostest.library"
    fd = read_lib_fd(name)
    ctx = _create_ctx()
    log_missing = logging.getLogger("missing")
    log_valid = logging.getLogger("valid")
    profile = LibProfileData(fd)
    # create stub
    gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)
    stub = gen.gen_fake_stub(name, fd, ctx, profile)
    _check_stub(stub)
    # call func
    stub.PrintHello()
    stub.Dummy()
    stub.Swap()
    stub.PrintString()
    _check_log_fake(caplog)
    _check_profile(fd, profile)
