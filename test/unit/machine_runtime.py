import pytest

from machine68k import CPUType
from amitools.vamos.machine import Machine, Runtime, ResetOpcodeError
from amitools.vamos.machine.opcodes import op_rts, op_jsr, op_reset, op_nop
from amitools.vamos.log import log_machine


def create_runtime(cpu_type=CPUType.M68000, supervisor=False):
    m = Machine(cpu_type, supervisor=supervisor)
    cpu = m.get_cpu()
    mem = m.get_mem()
    code = m.get_ram_begin()
    stack = m.get_scratch_top()
    r = Runtime(m)
    return r, m, cpu, mem, code, stack


def machine_runtime_rts_test():
    r, m, cpu, mem, code, stack = create_runtime()
    # single RTS to immediately return from run
    mem.w16(code, op_rts)
    r.start(code, stack)
    m.cleanup()


def machine_runtime_trap_test():
    r, m, cpu, mem, code, stack = create_runtime()
    a = []

    def func(op, pc):
        a.append("hello")

    addr = m.setup_quick_trap(func)
    # jump to trap
    mem.w16(code, op_jsr)
    mem.w32(code + 2, addr)
    # return
    mem.w16(code + 6, op_rts)
    r.start(code, stack)
    m.cleanup()
    # make sure trap was hit
    assert a == ["hello"]


def machine_runtime_trap_exception_test():
    r, m, cpu, mem, code, stack = create_runtime()
    error = ValueError("bla")

    def func(op, pc):
        raise error

    addr = m.setup_quick_trap(func)
    # jump to trap
    mem.w16(code, op_jsr)
    mem.w32(code + 2, addr)
    # return
    mem.w16(code + 6, op_rts)
    # exception triggers when the trap is executed directly in the run loop
    with pytest.raises(ValueError):
        r.start(code, stack)
    m.cleanup()


def machine_runtime_nested_run_test():
    r, m, cpu, mem, code, stack = create_runtime()

    def func(op, pc):
        r.nested_run(code + 10)

    addr = m.setup_quick_trap(func)
    # jump to trap
    mem.w16(code, op_jsr)
    mem.w32(code + 2, addr)
    # return
    mem.w16(code + 6, op_rts)
    # 2nd run
    mem.w16(code + 10, op_rts)
    r.start(code, stack)
    m.cleanup()


def machine_runtime_nested_run_error_test():
    r, m, cpu, mem, code, stack = create_runtime(supervisor=True)

    def func(op, pc):
        r.nested_run(code + 10)

    addr = m.setup_quick_trap(func)
    # jump to trap
    mem.w16(code, op_jsr)
    mem.w32(code + 2, addr)
    # return
    mem.w16(code + 6, op_rts)
    # 2nd run
    mem.w16(code + 10, op_reset)
    # the reset opcode error is passed through
    with pytest.raises(ResetOpcodeError):
        r.start(code, stack)
    m.cleanup()


def machine_runtime_nested_run_trap_test():
    r, m, cpu, mem, code, stack = create_runtime()
    a = []

    def func2(op, pc):
        a.append("foo")

    def func(op, pc):
        r.nested_run(code + 10)

    addr = m.setup_quick_trap(func)
    addr2 = m.setup_quick_trap(func2)
    # jump to trap
    mem.w16(code, op_jsr)
    mem.w32(code + 2, addr)
    # return
    mem.w16(code + 6, op_rts)
    # 2nd run
    mem.w16(code + 10, op_jsr)
    mem.w32(code + 12, addr2)
    mem.w16(code + 16, op_rts)
    # start
    r.start(code, stack)
    m.cleanup()
    assert a == ["foo"]


def machine_runtime_nested_run_trap_exception_test():
    r, m, cpu, mem, code, stack = create_runtime()
    error = ValueError("bla")

    def func2(op, pc):
        raise error

    def func(op, pc):
        r.nested_run(code + 10)

    addr = m.setup_quick_trap(func)
    addr2 = m.setup_quick_trap(func2)
    # jump to trap
    mem.w16(code, op_jsr)
    mem.w32(code + 2, addr)
    # return
    mem.w16(code + 6, op_rts)
    # 2nd run
    mem.w16(code + 10, op_jsr)
    mem.w32(code + 12, addr2)
    mem.w16(code + 16, op_rts)
    # start
    # exception triggers when the trap is executed directly in the run loop
    with pytest.raises(ValueError):
        r.start(code, stack)
    m.cleanup()


def machine_runtime_max_cycle_hook_test():
    r, m, cpu, mem, code, stack = create_runtime()

    cycle_reports = []

    def hook(*args):
        cycle_reports.append(args)

    r.set_max_cycle_hook(hook)

    def func2(op, pc):
        rs = r.get_current_run_state()
        assert rs.cycles > 0

    def func(op, pc):
        rs = r.get_current_run_state()
        assert rs.cycles > 0
        r.nested_run(code + 200, name="foo")

    addr = m.setup_quick_trap(func)
    addr2 = m.setup_quick_trap(func2)

    # first code
    for i in range(0, 100, 2):
        mem.w16(code + i, op_nop)
    mem.w16(code + 100, op_jsr)
    mem.w32(code + 102, addr)
    mem.w16(code + 106, op_rts)

    # first code
    for i in range(110, 200, 2):
        mem.w16(code + i, op_nop)
    mem.w16(code + 200, op_jsr)
    mem.w32(code + 202, addr2)
    mem.w16(code + 206, op_rts)

    # start
    r.start(code, stack, name="go", max_cycles=100)
    m.cleanup()

    # check cycle reports
    assert len(cycle_reports) > 0
    for report in cycle_reports:
        assert report[0] > 100
