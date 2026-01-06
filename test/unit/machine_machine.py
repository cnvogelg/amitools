import pytest
import logging

from amitools.vamos.machine import (
    Machine,
    InvalidMemoryAccessError,
    CPUHWExceptionError,
    ResetOpcodeError,
)
from amitools.vamos.machine.opcodes import op_rts, op_reset, op_trap0, op_jmp
from amitools.vamos.log import log_machine
from amitools.vamos.cfgcore import ConfigDict


log_machine.setLevel(logging.DEBUG)


class Context:
    def __init__(self, mach):
        self.mach = mach
        self.mem = self.mach.mem
        self.cpu = self.mach.cpu
        self.traps = self.mach.traps

        self.code = mach.get_ram_begin()
        self.stack = mach.get_scratch_top()
        mach.prepare(self.code, self.stack)

    def cleanup(self):
        self.mach.cleanup()


@pytest.fixture
def ctx():
    mach = Machine()
    return Context(mach)


@pytest.fixture
def ctx_super():
    mach = Machine(supervisor=True)
    return Context(mach)


def machine_machine_execute_rts_test(ctx):
    """simple minimal rts code to test machine execution"""
    # single RTS to immediately return from run
    ctx.mem.w16(ctx.code, op_rts)
    er = ctx.mach.execute()
    assert er.cycles == 20
    assert ctx.mach.was_exit(er)
    ctx.mach.cleanup()


def machine_machine_execute_instr_hook_test(ctx):
    """test the instruction hook"""
    a = []
    # set instr hook

    def my_hook(pc):
        a.append(pc)

    ctx.mach.set_instr_hook(my_hook)
    # single RTS to immediately return from run
    ctx.mem.w16(ctx.code, op_rts)
    er = ctx.mach.execute()
    assert er.cycles == 20
    assert ctx.mach.was_exit(er)
    assert a == [0x1000, 0x400]
    ctx.mach.cleanup()


def machine_machine_execute_mem_trace_test(ctx):
    """test memory tracing during execution"""
    a = []
    # set instr hook

    def my_trace(*args):
        a.append(args)

    ctx.mach.set_cpu_mem_trace_hook(my_trace)
    # single RTS to immediately return from run
    ctx.mem.w16(ctx.code, op_rts)
    er = ctx.mach.execute()
    assert er.cycles == 20
    assert ctx.mach.was_exit(er)
    assert a[0] == ("R", 1, ctx.code, op_rts)
    ctx.mach.cleanup()


def machine_machine_execute_mem_addr_error_test(ctx):
    """trigger a memory address error"""
    ctx.mach.prepare(0xF80000, ctx.stack)
    with pytest.raises(InvalidMemoryAccessError) as ei:
        ctx.mach.execute()
    exc = ei.value
    assert exc.pc == 0xF80004
    assert exc.mode == "R"
    assert exc.width == 1
    assert exc.addr == 0xF80002
    ctx.mach.cleanup()


def machine_machine_execute_mem_addr_error_handle_test(ctx):
    """handle a memory address error"""

    def handle_addr_error(exc):
        assert type(exc) is InvalidMemoryAccessError
        return True

    ctx.mach.set_addr_err_hook(handle_addr_error)

    ctx.mach.prepare(0xF80000, ctx.stack)
    er = ctx.mach.execute(100)
    assert er.cycles == 104
    ctx.mach.cleanup()


# --- traps ---


def machine_machine_execute_trap_simple_test(ctx):
    """trigger a trap function"""
    a = []

    def func(op, pc):
        a.append("hello")

    addr = ctx.mach.setup_quick_trap(func)
    ctx.mach.prepare(addr, ctx.stack)
    er = ctx.mach.execute()
    assert er.cycles == 24
    assert a == ["hello"]
    ctx.mach.cleanup()


def machine_machine_execute_trap_exception_test(ctx):
    """raise exception inside trap function"""
    error = ValueError("bla")

    def func(op, pc):
        raise error

    addr = ctx.mach.setup_quick_trap(func)
    ctx.mach.prepare(addr, ctx.stack)
    with pytest.raises(ValueError):
        # execute will propagate the exception
        ctx.mach.execute()
    ctx.mach.cleanup()


def machine_machine_execute_trap_unbound_test(ctx):
    """unknown ALINE trap raises ALINE CPU HW exception"""
    # place an unbound trap -> raise ALINE exception
    ctx.mem.w16(ctx.code, 0xA100)
    # single RTS to immediately return from run
    ctx.mem.w16(ctx.code + 2, op_rts)
    with pytest.raises(CPUHWExceptionError) as ei:
        ctx.mach.execute()
    exc = ei.value
    assert exc.pc == ctx.code
    ctx.mach.cleanup()


# --- reset opcode ---


def machine_machine_execute_reset_opcode_exception_test(ctx_super):
    """RESET opcode test -> raise exception if unhandled"""
    # place a reset opcode
    ctx = ctx_super
    ctx.mem.w16(ctx.code, op_reset)
    ctx.mem.w16(ctx.code + 2, op_rts)
    with pytest.raises(ResetOpcodeError) as ei:
        ctx.mach.execute()
    exc = ei.value
    assert exc.pc == ctx.code
    ctx.mach.cleanup()


def machine_machine_execute_reset_opcode_handle_test(ctx_super):
    """if RESET handler is set then trigger that"""

    def handle_reset_opcode(error):
        assert type(error) is ResetOpcodeError
        # True means accept error and continue execution
        return True

    # set handler to accept reset opcode
    ctx = ctx_super
    ctx.mach.set_reset_hook(handle_reset_opcode)

    # place a reset opcode
    ctx.mem.w16(ctx.code, op_reset)
    ctx.mem.w16(ctx.code + 2, op_rts)
    er = ctx.mach.execute()
    assert ctx.mach.was_exit(er)

    ctx.mach.cleanup()


# --- HW Trap #0 ---


def machine_machine_execute_hw_trap0_raise_test(ctx):
    # trigger a "real" trap #0
    ctx.mem.w16(ctx.code, op_trap0)
    with pytest.raises(CPUHWExceptionError) as ei:
        ctx.mach.execute()
    exc = ei.value
    assert exc.pc == ctx.code + 2
    assert exc.exc_num == 32  # trap0 exception number
    ctx.mach.cleanup()


def machine_machine_execute_hw_trap0_handle_test(ctx):

    def handle_trap(error):
        assert type(error) is CPUHWExceptionError
        assert error.pc == ctx.code + 2
        assert error.exc_num == 32
        return True

    # allow to handle trap
    ctx.mach.set_hw_exc_hook(handle_trap)

    # trigger a "real" trap #0
    ctx.mem.w16(ctx.code, op_trap0)
    ctx.mem.w16(ctx.code + 2, op_rts)

    er = ctx.mach.execute()
    assert ctx.mach.was_exit(er)

    ctx.mach.cleanup()


# --- max cycles --


def machine_machine_execute_max_cycles_test(ctx):
    """check max cycles execution"""
    ctx.mem.w16(ctx.code, op_jmp)
    ctx.mem.w32(ctx.code + 2, ctx.code)
    er = ctx.mach.execute(200)
    assert not er.result
    assert not ctx.mach.was_exit(er)
    assert er.cycles == 204
    ctx.mach.cleanup()


# --- config test ---


def machine_machine_cfg_test():
    cfg = ConfigDict(
        {"cpu": "68020", "ram_size": 2048, "hw_exc": None, "backend": None}
    )
    m = Machine.from_cfg(cfg, True)
    assert m
    assert m.get_cpu_name() == "68020"
    assert m.get_ram_total_kib() == 2048
    assert m.get_label_mgr()
