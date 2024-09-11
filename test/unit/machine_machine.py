import pytest
import logging

from machine68k import CPUType
from amitools.vamos.machine import Machine, ExecutionStatus, TrapCall
from amitools.vamos.machine.opcodes import *
from amitools.vamos.error import *
from amitools.vamos.log import log_machine
from amitools.vamos.cfgcore import ConfigDict


log_machine.setLevel(logging.DEBUG)


def create_machine(cpu_type=CPUType.M68000):
    m = Machine(cpu_type)
    cpu = m.get_cpu()
    mem = m.get_mem()
    code = m.get_ram_begin()
    stack = m.get_scratch_top()
    m.set_start(code, stack)
    m.set_end()
    return m, cpu, mem, code, stack


def machine_machine_execute_rts_test():
    m, cpu, mem, code, stack = create_machine()
    # single RTS to immediately return from run
    mem.w16(code, op_rts)
    rs = m.execute()
    assert rs.status == ExecutionStatus.EXIT_CODE
    assert rs.error is None
    assert rs.trap is None
    m.cleanup()


def machine_machine_instr_hook_test():
    m, cpu, mem, code, stack = create_machine()
    a = []
    # set instr hook

    def my_hook():
        pc = cpu.r_pc()
        a.append(pc)

    m.set_instr_hook(my_hook)
    # single RTS to immediately return from run
    mem.w16(code, op_rts)
    rs = m.execute()
    assert rs.status == ExecutionStatus.EXIT_CODE
    assert rs.error is None
    assert rs.trap is None
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
    rs = m.execute()
    assert rs.status == ExecutionStatus.EXIT_CODE
    assert rs.error is None
    assert rs.trap is None
    assert a[0] == ("R", 1, code, op_rts)
    m.cleanup()


def machine_machine_execute_mem_invalid_test(caplog):
    m, cpu, mem, code, stack = create_machine()
    a = []
    m.set_start(0xF80000, stack)
    rs = m.execute()
    assert rs.status == ExecutionStatus.ERROR
    assert type(rs.error) == InvalidMemoryAccessError
    m.cleanup()
    log = caplog.record_tuples
    assert (
        "machine",
        logging.ERROR,
        "invalid memory access: mode=R width=1 addr=f80000",
    ) in log


def machine_machine_execute_trap_test():
    m, cpu, mem, code, stack = create_machine()
    error = ValueError("bla")
    a = []

    def func(op, pc):
        a.append("hello")

    addr = m.setup_quick_trap(func)
    m.set_start(addr, stack)
    rs = m.execute()
    assert rs.status == ExecutionStatus.TRAP
    assert rs.error is None
    assert type(rs.trap) is TrapCall
    assert rs.trap.func is func
    # trigger exception
    rs.trap.call()
    assert a == ["hello"]
    m.cleanup()


def machine_machine_execute_trap_exception_test():
    m, cpu, mem, code, stack = create_machine()
    error = ValueError("bla")

    def func(op, pc):
        raise error

    addr = m.setup_quick_trap(func)
    m.set_start(addr, stack)
    rs = m.execute()
    assert rs.status == ExecutionStatus.TRAP
    assert rs.error is None
    assert type(rs.trap) is TrapCall
    assert rs.trap.func is func
    # exception triggers when the trap is executed later
    with pytest.raises(ValueError):
        rs.trap.call()
    m.cleanup()


def machine_machine_execute_trap_unbound_test():
    m, cpu, mem, code, stack = create_machine()
    # place an unbound trap -> raise ALINE exception
    mem.w16(code, 0xA100)
    # single RTS to immediately return from run
    mem.w16(code + 2, op_rts)
    rs = m.execute()
    assert rs.status == ExecutionStatus.ERROR
    assert type(rs.error) is InvalidCPUStateError
    assert rs.error.pc == code
    m.cleanup()


def machine_machine_execute_reset_opcode_test():
    m, cpu, mem, code, stack = create_machine()
    # place a reset opcode
    mem.w16(code, op_reset)
    mem.w16(code + 2, op_rts)
    rs = m.execute()
    assert rs.status == ExecutionStatus.ERROR
    assert type(rs.error) is InvalidCPUStateError
    assert rs.error.pc == code
    m.cleanup()


def machine_machine_execute_hw_exc_test():
    m, cpu, mem, code, stack = create_machine()
    # trigger a "real" trap #0
    mem.w16(code, 0x4E40)
    rs = m.execute()
    assert rs.status == ExecutionStatus.ERROR
    assert type(rs.error) is InvalidCPUStateError
    assert rs.error.pc == code + 2
    m.cleanup()


def machine_machine_execute_max_cycles_test():
    m, cpu, mem, code, stack = create_machine()
    mem.w16(code, op_jmp)
    mem.w32(code + 2, code)
    rs = m.execute(200)
    assert rs.status == ExecutionStatus.MAX_CYCLES
    assert rs.error is None
    m.cleanup()


def machine_machine_cfg_test():
    cfg = ConfigDict({"cpu": "68020", "ram_size": 2048})
    m = Machine.from_cfg(cfg, True)
    assert m
    assert m.get_cpu_type() == CPUType.M68020
    assert m.get_cpu_name() == "68020"
    assert m.get_ram_total_kib() == 2048
    assert m.get_label_mgr()
