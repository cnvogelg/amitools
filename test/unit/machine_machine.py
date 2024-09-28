import pytest
import logging

from machine68k import CPUType
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


def create_machine(cpu_type=CPUType.M68000, supervisor=False):
    m = Machine(cpu_type, supervisor=supervisor)
    cpu = m.get_cpu()
    mem = m.get_mem()
    code = m.get_ram_begin()
    stack = m.get_scratch_top()
    m.prepare(code, stack)
    return m, cpu, mem, code, stack


def machine_machine_execute_rts_test():
    m, cpu, mem, code, stack = create_machine()
    # single RTS to immediately return from run
    mem.w16(code, op_rts)
    er = m.execute()
    assert er.cycles == 20
    m.cleanup()


def machine_machine_instr_hook_test():
    m, cpu, mem, code, stack = create_machine()
    a = []
    # set instr hook

    def my_hook(pc):
        a.append(pc)

    m.set_instr_hook(my_hook)
    # single RTS to immediately return from run
    mem.w16(code, op_rts)
    er = m.execute()
    assert er.cycles == 20
    assert a == [0x800, 0x400]
    m.cleanup()


def machine_machine_execute_mem_trace_test():
    m, cpu, mem, code, stack = create_machine()
    a = []
    # set instr hook

    def my_trace(*args):
        a.append(args)

    m.set_cpu_mem_trace_hook(my_trace)
    # single RTS to immediately return from run
    mem.w16(code, op_rts)
    er = m.execute()
    assert er.cycles == 20
    assert a[0] == ("R", 1, code, op_rts)
    m.cleanup()


def machine_machine_execute_mem_invalid_test():
    m, cpu, mem, code, stack = create_machine()
    a = []
    m.prepare(0xF80000, stack)
    with pytest.raises(InvalidMemoryAccessError) as ei:
        er = m.execute()
    exc = ei.value
    assert exc.pc == 0xF80004
    assert exc.mode == "R"
    assert exc.width == 1
    assert exc.addr == 0xF80002
    m.cleanup()


def machine_machine_execute_trap_test():
    m, cpu, mem, code, stack = create_machine()
    a = []

    def func(op, pc):
        a.append("hello")

    addr = m.setup_quick_trap(func)
    m.prepare(addr, stack)
    er = m.execute()
    assert er.cycles == 24
    assert a == ["hello"]
    m.cleanup()


def machine_machine_execute_trap_exception_test():
    m, cpu, mem, code, stack = create_machine()
    error = ValueError("bla")

    def func(op, pc):
        raise error

    addr = m.setup_quick_trap(func)
    m.prepare(addr, stack)
    with pytest.raises(ValueError):
        er = m.execute()
    m.cleanup()


def machine_machine_execute_trap_unbound_test():
    m, cpu, mem, code, stack = create_machine()
    # place an unbound trap -> raise ALINE exception
    mem.w16(code, 0xA100)
    # single RTS to immediately return from run
    mem.w16(code + 2, op_rts)
    with pytest.raises(CPUHWExceptionError) as ei:
        er = m.execute()
    exc = ei.value
    assert exc.pc == code
    m.cleanup()


def machine_machine_execute_reset_opcode_test():
    m, cpu, mem, code, stack = create_machine(supervisor=True)
    # place a reset opcode
    mem.w16(code, op_reset)
    with pytest.raises(ResetOpcodeError) as ei:
        er = m.execute()
    exc = ei.value
    assert exc.pc == code
    m.cleanup()


def machine_machine_execute_hw_exc_test():
    m, cpu, mem, code, stack = create_machine()
    # trigger a "real" trap #0
    mem.w16(code, op_trap0)
    with pytest.raises(CPUHWExceptionError) as ei:
        er = m.execute()
    exc = ei.value
    assert exc.pc == code + 2
    m.cleanup()


def machine_machine_execute_max_cycles_test():
    m, cpu, mem, code, stack = create_machine()
    mem.w16(code, op_jmp)
    mem.w32(code + 2, code)
    er = m.execute(200)
    assert er.cycles == 204
    m.cleanup()


def machine_machine_cfg_test():
    cfg = ConfigDict({"cpu": "68020", "ram_size": 2048})
    m = Machine.from_cfg(cfg, True)
    assert m
    assert m.get_cpu_type() == CPUType.M68020
    assert m.get_cpu_name() == "68020"
    assert m.get_ram_total_kib() == 2048
    assert m.get_label_mgr()
