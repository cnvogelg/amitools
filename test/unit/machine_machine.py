from amitools.vamos.machine import Machine, CPUState
from amitools.vamos.machine.opcodes import *
from amitools.vamos.error import *
from amitools.vamos.log import log_machine
from amitools.vamos.cfgcore import ConfigDict
import logging


log_machine.setLevel(logging.DEBUG)


def create_machine(cpu_type=Machine.CPU_TYPE_68000):
    m = Machine(cpu_type, raise_on_main_run=False)
    cpu = m.get_cpu()
    mem = m.get_mem()
    code = m.get_ram_begin()
    stack = m.get_scratch_top()
    return m, cpu, mem, code, stack


def machine_machine_run_rts_test():
    m, cpu, mem, code, stack = create_machine()
    # single RTS to immediately return from run
    mem.w16(code, op_rts)
    rs = m.run(code, stack)
    assert rs.done
    assert rs.error is None
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
    rs = m.run(code, stack)
    assert rs.done
    assert rs.error is None
    assert a == [0x800, 0x400]
    m.cleanup()


def machine_machine_cpu_mem_trace_test():
    m, cpu, mem, code, stack = create_machine()
    a = []
    # set instr hook

    def my_trace(*args):
        a.append(args)

    m.set_cpu_mem_trace_hook(my_trace)
    # single RTS to immediately return from run
    mem.w16(code, op_rts)
    rs = m.run(code, stack)
    assert rs.done
    assert rs.error is None
    print(a)
    assert a[0] == ("R", 1, code, op_rts)
    m.cleanup()


def machine_machine_cpu_mem_invalid_test(caplog):
    m, cpu, mem, code, stack = create_machine()
    a = []
    rs = m.run(0xF80000, stack)
    assert rs.done
    assert type(rs.error) == InvalidMemoryAccessError
    m.cleanup()
    log = caplog.record_tuples
    assert ("machine", logging.ERROR, "----- ERROR in CPU Run #1 -----") in log
    assert (
        "machine",
        logging.ERROR,
        "InvalidMemoryAccessError: Invalid Memory Access R(2): f80000",
    ) in log


def machine_machine_run_nested_ok_test():
    m, cpu, mem, code, stack = create_machine()
    a = []
    res = []

    def nested2(op, pc):
        a.append(3)

    addr2 = m.setup_quick_trap(nested2)

    def nested(op, pc):
        a.append(1)
        rs = m.run(addr2)
        res.append(rs)
        a.append(2)

    addr = m.setup_quick_trap(nested)
    rs = m.run(addr, stack)
    assert rs.done
    assert rs.error is None
    assert a == [1, 3, 2]
    rs2 = res[0]
    assert rs2.done
    assert rs2.error is None
    m.cleanup()


def machine_machine_run_raise_test():
    m, cpu, mem, code, stack = create_machine()
    error = ValueError("bla")

    def nested(op, pc):
        raise error

    addr = m.setup_quick_trap(nested)
    rs = m.run(addr, stack)
    assert rs.done
    assert rs.error == error
    m.cleanup()


def machine_machine_run_raise2_test():
    m, cpu, mem, code, stack = create_machine()
    error = ValueError("bla")

    def nested(op, pc):
        raise error

    addr = m.setup_quick_trap(nested)
    mem.w16(code, op_jmp)
    mem.w32(code + 2, addr)
    mem.w16(code + 6, op_nop)
    mem.w16(code + 8, op_rts)
    rs = m.run(code, stack)
    assert rs.done
    assert rs.error == error
    m.cleanup()


def machine_machine_run_nested_raise_test():
    m, cpu, mem, code, stack = create_machine()
    a = []
    res = []
    error = ValueError("bla")

    def nested2(op, pc):
        raise error

    ncode = code + 0x100
    addr2 = m.setup_quick_trap(nested2)
    mem.w16(ncode, op_jmp)
    mem.w32(ncode + 2, addr2)
    mem.w16(ncode + 6, op_nop)
    mem.w16(ncode + 8, op_rts)

    def nested(op, pc):
        a.append(1)
        rs = m.run(ncode)
        res.append(rs)
        a.append(2)

    addr = m.setup_quick_trap(nested)
    mem.w16(code, op_jmp)
    mem.w32(code + 2, addr)
    mem.w16(code + 6, op_nop)
    mem.w16(code + 8, op_rts)

    rs = m.run(code, stack)
    assert rs.done
    assert type(rs.error) is NestedCPURunError
    assert rs.error.error == error
    assert a == [1]
    m.cleanup()


def machine_machine_run_trap_unbound_test():
    m, cpu, mem, code, stack = create_machine()
    # place an unbound trap -> raise ALINE exception
    mem.w16(code, 0xA100)
    # single RTS to immediately return from run
    mem.w16(code + 2, op_rts)
    rs = m.run(code, stack)
    assert rs.done
    assert type(rs.error) is InvalidCPUStateError
    assert rs.error.pc == code
    m.cleanup()


def machine_machine_run_reset_test():
    m, cpu, mem, code, stack = create_machine()
    # place a reset opcode
    mem.w16(code, op_reset)
    mem.w16(code + 2, op_rts)
    rs = m.run(code, stack)
    assert rs.done
    assert type(rs.error) is InvalidCPUStateError
    assert rs.error.pc == code
    m.cleanup()


def machine_machine_run_addr_exc_test():
    # check for address exception
    # currently disabled in musashi!
    m, cpu, mem, code, stack = create_machine()
    m.show_instr()
    # move.l $1,d4
    mem.w32(code, 0x28380001)
    mem.w16(code + 4, op_rts)
    rs = m.run(code, stack)
    assert rs.done
    assert rs.error is None
    m.cleanup()


def machine_machine_cfg_test():
    cfg = ConfigDict(
        {"cpu": "68020", "ram_size": 2048, "max_cycles": 128, "cycles_per_run": 2000}
    )
    m = Machine.from_cfg(cfg, True)
    assert m
    assert m.get_cpu_type() == Machine.CPU_TYPE_68020
    assert m.get_cpu_name() == "68020"
    assert m.get_ram_total_kib() == 2048
    assert m.max_cycles == 128
    assert m.cycles_per_run == 2000
    assert m.get_label_mgr()
