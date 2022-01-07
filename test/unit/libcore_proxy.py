import pytest

from amitools.vamos.libcore import LibCtx, LibProxyGen
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary
from amitools.vamos.machine import MockMachine
from amitools.fd import read_lib_fd
from amitools.vamos.machine.regs import *


def _create_ctx():
    machine = MockMachine()
    return LibCtx(machine)


def _create_fd():
    name = "vamostest.library"
    impl = VamosTestLibrary()
    fd = read_lib_fd(name)
    return fd


class MyStub:
    def __init__(self, ctx):
        self.ctx = ctx
        self.hello_count = 0
        self.hello_kwargs = None
        self.string_count = 0
        self.string_kwargs = None
        self.string_reg_a0 = None

    def PrintHello(self, **kwargs):
        self.hello_count += 1
        self.hello_kwargs = kwargs
        self.ctx.cpu.w_reg(REG_D0, self.hello_count)

    def PrintString(self, **kwargs):
        self.string_count += 1
        self.string_kwargs = kwargs
        self.string_reg_a0 = self.ctx.cpu.r_reg(REG_A0)
        self.ctx.cpu.w_reg(REG_D0, self.string_count)
        self.ctx.cpu.w_reg(REG_D1, 2 * self.string_count)


class MyMachine:
    def __init__(self):
        self.pc = None
        self.sp = None
        self.set_regs = None
        self.get_regs = None
        self.name = None
        self.regs = None

    def run(self, pc, sp=None, set_regs=None, get_regs=None, name=None):
        self.pc = pc
        self.sp = sp
        self.set_regs = set_regs
        self.get_regs = get_regs
        self.name = name
        if len(get_regs) == 2:
            self.regs = {REG_D0: 23, REG_D1: 42}
        else:
            self.regs = {REG_D0: 11}
        return self


def libcore_proxy_gen_stub_test():
    ctx = _create_ctx()
    lib_fd = _create_fd()
    gen = LibProxyGen()
    stub = MyStub(ctx)
    # generate proxy type
    VamosTestProxy = gen.gen_proxy_for_stub("VamosTestProxy", lib_fd, stub)
    # check some functions
    type_dict = VamosTestProxy.__dict__
    assert "PrintString" in type_dict
    assert "PrintHello" in type_dict
    # create proxy instance
    proxy = VamosTestProxy(ctx)
    # call hello
    assert stub.hello_count == 0
    ret = proxy.PrintHello()
    assert ret == 1
    assert stub.hello_count == 1
    assert ctx.cpu.r_reg(REG_D0) == stub.hello_count
    # call hello with kwargs
    assert stub.hello_count == 1
    ret = proxy.PrintHello(what="why")
    assert ret == 2
    assert stub.hello_count == 2
    assert stub.hello_kwargs == {"what": "why"}
    assert ctx.cpu.r_reg(REG_D0) == stub.hello_count
    # call string
    assert stub.string_count == 0
    ret = proxy.PrintString(0x10, ret_d1=True)
    assert ret == (1, 2)
    assert stub.string_count == 1
    assert stub.string_reg_a0 == 0x10
    assert ctx.cpu.r_reg(REG_D0) == stub.string_count
    assert ctx.cpu.r_reg(REG_D1) == stub.string_count * 2
    # call string with kwargs
    assert stub.string_count == 1
    ret = proxy.PrintString(0x20, ret_d1=True, foo="bar")
    assert ret == (2, 4)
    assert stub.string_count == 2
    assert stub.string_reg_a0 == 0x20
    assert stub.string_kwargs == {"foo": "bar"}
    assert ctx.cpu.r_reg(REG_D0) == stub.string_count
    assert ctx.cpu.r_reg(REG_D1) == stub.string_count * 2
    # ensure that positional arguments are here
    with pytest.raises(AssertionError):
        proxy.PrintString()
    with pytest.raises(AssertionError):
        proxy.PrintString(1, 2)


def libcore_proxy_gen_libcall_test():
    machine = MyMachine()
    ctx = _create_ctx()
    ctx.machine = machine
    lib_fd = _create_fd()
    gen = LibProxyGen()
    base_addr = 0x1000
    # gen prxoy
    VamosTestProxy = gen.gen_proxy_for_libcall("VamosTestProxy", lib_fd)
    # check some functions
    type_dict = VamosTestProxy.__dict__
    assert "PrintString" in type_dict
    assert "PrintHello" in type_dict
    # create proxy instance
    proxy = VamosTestProxy(ctx, base_addr)
    # call hello
    ret = proxy.PrintHello()
    assert ret == 11
    assert machine.set_regs == {}
    assert machine.get_regs == [REG_D0]
    # call string
    ret = proxy.PrintString(0x10, ret_d1=True)
    assert ret == (23, 42)
    assert machine.set_regs == {REG_A0: 0x10}
    assert machine.get_regs == [REG_D0, REG_D1]
    # ensure that positional arguments are here
    with pytest.raises(AssertionError):
        proxy.PrintString()
    with pytest.raises(AssertionError):
        proxy.PrintString(1, 2)
