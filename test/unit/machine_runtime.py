import pytest

from amitools.vamos.machine import (
    Machine,
    Runtime,
    Code,
    ResetOpcodeError,
    REG_D1,
    REG_D0,
)
from amitools.vamos.machine.opcodes import op_rts, op_jsr, op_reset, op_nop


class Context:
    def __init__(self, supervisor=False, run_cycles=1000):
        self.mach = Machine(supervisor=supervisor)
        self.cpu = self.mach.get_cpu()
        self.mem = self.mach.get_mem()
        self.code = self.mach.get_ram_begin()
        self.stack = self.mach.get_scratch_top()
        self.pc_sp = Code(self.code, self.stack)
        self.rt = Runtime(self.mach, run_cycles=run_cycles)

    def cleanup(self):
        self.mach.cleanup()


@pytest.fixture
def ctx():
    return Context()


@pytest.mark.parametrize("run_cycles", (10, 20, 40, 80, 100, 200, 500, 1000))
def machine_runtime_rts_test(run_cycles, ctx):
    # single RTS to immediately return from run
    ctx.mem.w16(ctx.code, op_rts)
    rs = ctx.rt.start(ctx.pc_sp)
    assert rs.exit
    assert rs.pc == ctx.mach.get_run_exit_addr() + 2
    assert rs.nesting == 0
    assert rs.cycles == 20
    ctx.cleanup()


def machine_runtime_trap_test(ctx):
    """call a trap"""
    a = []

    def func(op, pc):
        a.append("hello")

    addr = ctx.mach.setup_quick_trap(func)
    # jump to trap
    ctx.mem.w16(ctx.code, op_jsr)
    ctx.mem.w32(ctx.code + 2, addr)
    # return
    ctx.mem.w16(ctx.code + 6, op_rts)
    rs = ctx.rt.start(ctx.pc_sp)
    # check run state
    assert rs.pc == ctx.mach.get_run_exit_addr() + 2
    assert rs.exit
    # cleanup
    ctx.cleanup()
    # make sure trap was hit
    assert a == ["hello"]


def machine_runtime_trap_set_get_regs_test(ctx):
    """start run and set/get regs"""

    def func(op, pc):
        d0 = ctx.cpu.r_reg(REG_D0)
        d1 = ctx.cpu.r_reg(REG_D1)
        assert d0 == 1234
        assert d1 == 5678
        ctx.cpu.w_reg(REG_D0, 0xCAFE)
        ctx.cpu.w_reg(REG_D1, 0xBABE)

    addr = ctx.mach.setup_quick_trap(func)
    # jump to trap
    ctx.mem.w16(ctx.code, op_jsr)
    ctx.mem.w32(ctx.code + 2, addr)
    # return
    ctx.mem.w16(ctx.code + 6, op_rts)
    # setup regs
    set_regs = {REG_D0: 1234, REG_D1: 5678}
    get_regs = [REG_D0, REG_D1]
    rs = ctx.rt.start(Code(ctx.code, ctx.stack, set_regs=set_regs, get_regs=get_regs))
    ctx.cleanup()
    assert rs.regs == {REG_D0: 0xCAFE, REG_D1: 0xBABE}


def machine_runtime_trap_exception_test(ctx):
    error = ValueError("bla")

    def func(op, pc):
        raise error

    addr = ctx.mach.setup_quick_trap(func)
    # jump to trap
    ctx.mem.w16(ctx.code, op_jsr)
    ctx.mem.w32(ctx.code + 2, addr)
    # return
    ctx.mem.w16(ctx.code + 6, op_rts)
    # exception triggers when the trap is executed directly in the run loop
    with pytest.raises(ValueError):
        ctx.rt.start(ctx.pc_sp)
    ctx.cleanup()


def machine_runtime_nested_run_test(ctx):

    def func(op, pc):
        # check current run state before
        rs = ctx.rt.get_current_run_state()
        # pc is still the start of this run
        assert rs.pc == ctx.code
        assert rs.nesting == 0
        # issue nested run
        rs2 = ctx.rt.nested_run(Code(ctx.code + 10))
        assert rs2.exit
        # check current run state after
        rs = ctx.rt.get_current_run_state()
        # pc is still the start of this run
        assert rs.pc == ctx.code
        assert rs.nesting == 0

    addr = ctx.mach.setup_quick_trap(func)
    # jump to trap
    ctx.mem.w16(ctx.code, op_jsr)
    ctx.mem.w32(ctx.code + 2, addr)
    # return
    ctx.mem.w16(ctx.code + 6, op_rts)
    # 2nd run
    ctx.mem.w16(ctx.code + 10, op_rts)
    rs = ctx.rt.start(Code(ctx.code, ctx.stack))
    assert rs.exit
    assert rs.pc == ctx.mach.get_run_exit_addr() + 2
    ctx.cleanup()


def machine_runtime_nested_run_error_test():

    ctx = Context(supervisor=True)

    def func(op, pc):
        ctx.rt.nested_run(Code(ctx.code + 10))

    addr = ctx.mach.setup_quick_trap(func)
    # jump to trap
    ctx.mem.w16(ctx.code, op_jsr)
    ctx.mem.w32(ctx.code + 2, addr)
    # return
    ctx.mem.w16(ctx.code + 6, op_rts)
    # 2nd run
    ctx.mem.w16(ctx.code + 10, op_reset)
    # the reset opcode error is passed through
    rs = ctx.rt.start(Code(ctx.code, ctx.stack))
    assert type(rs.mach_error) is ResetOpcodeError
    ctx.cleanup()


def machine_runtime_nested_run_trap_test(ctx):
    a = []

    def func2(op, pc):
        # check current run state before
        rs = ctx.rt.get_current_run_state()
        # pc is still the start of this run
        assert rs.pc == ctx.code + 10
        assert rs.nesting == 1
        # do action
        a.append("foo")
        # check current run state after
        rs = ctx.rt.get_current_run_state()
        # pc is still the start of this run
        assert rs.pc == ctx.code + 10
        assert rs.nesting == 1

    def func(op, pc):
        # check current run state before
        rs = ctx.rt.get_current_run_state()
        # pc is still the start of this run
        assert rs.pc == ctx.code
        assert rs.nesting == 0
        # issue nested run
        rs2 = ctx.rt.nested_run(Code(ctx.code + 10))
        assert rs2.exit
        # check current run state after
        rs = ctx.rt.get_current_run_state()
        # pc is still the start of this run
        assert rs.pc == ctx.code
        assert rs.nesting == 0

    addr = ctx.mach.setup_quick_trap(func)
    addr2 = ctx.mach.setup_quick_trap(func2)
    # jump to trap
    ctx.mem.w16(ctx.code, op_jsr)
    ctx.mem.w32(ctx.code + 2, addr)
    # return
    ctx.mem.w16(ctx.code + 6, op_rts)
    # 2nd run
    ctx.mem.w16(ctx.code + 10, op_jsr)
    ctx.mem.w32(ctx.code + 12, addr2)
    ctx.mem.w16(ctx.code + 16, op_rts)
    # start
    rs = ctx.rt.start(Code(ctx.code, ctx.stack))
    assert rs.exit
    ctx.cleanup()
    assert a == ["foo"]


def machine_runtime_nested_run_set_get_regs_test(ctx):

    def func2(op, pc):
        d0 = ctx.cpu.r_reg(REG_D0)
        d1 = ctx.cpu.r_reg(REG_D1)
        assert d0 == 23
        assert d1 == 42
        ctx.cpu.w_reg(REG_D0, 11)
        ctx.cpu.w_reg(REG_D1, 22)

    def func(op, pc):
        set_regs = {REG_D0: 23, REG_D1: 42}
        get_regs = [REG_D0, REG_D1]
        rs = ctx.rt.nested_run(
            Code(ctx.code + 10, set_regs=set_regs, get_regs=get_regs)
        )
        assert rs.regs == {REG_D0: 11, REG_D1: 22}

    addr = ctx.mach.setup_quick_trap(func)
    addr2 = ctx.mach.setup_quick_trap(func2)
    # jump to trap
    ctx.mem.w16(ctx.code, op_jsr)
    ctx.mem.w32(ctx.code + 2, addr)
    # return
    ctx.mem.w16(ctx.code + 6, op_rts)
    # 2nd run
    ctx.mem.w16(ctx.code + 10, op_jsr)
    ctx.mem.w32(ctx.code + 12, addr2)
    ctx.mem.w16(ctx.code + 16, op_rts)
    # start
    rs = ctx.rt.start(Code(ctx.code, ctx.stack))
    assert rs.exit
    ctx.cleanup()


def machine_runtime_nested_run_trap_exception_test(ctx):
    error = ValueError("bla")

    def func2(op, pc):
        raise error

    def func(op, pc):
        rs = ctx.rt.nested_run(Code(ctx.code + 10))
        assert rs.exit

    addr = ctx.mach.setup_quick_trap(func)
    addr2 = ctx.mach.setup_quick_trap(func2)
    # jump to trap
    ctx.mem.w16(ctx.code, op_jsr)
    ctx.mem.w32(ctx.code + 2, addr)
    # return
    ctx.mem.w16(ctx.code + 6, op_rts)
    # 2nd run
    ctx.mem.w16(ctx.code + 10, op_jsr)
    ctx.mem.w32(ctx.code + 12, addr2)
    ctx.mem.w16(ctx.code + 16, op_rts)
    # start
    # exception triggers when the trap is executed directly in the run loop
    with pytest.raises(ValueError) as ei:
        ctx.rt.start(Code(ctx.code, ctx.stack))
    assert ei.value == error
    ctx.cleanup()


@pytest.mark.parametrize("slice_cycles", (10, 20, 40, 80, 100, 200))
def machine_runtime_slice_hook_test(slice_cycles, ctx):

    slice_reports = []

    def hook(rs):
        slice_reports.append(rs)

    ctx.rt.set_slice_hook(slice_cycles, hook)

    def func2(op, pc):
        rs = ctx.rt.get_current_run_state()
        # cycles is not updated yet
        assert rs.cycles == 400

    def func(op, pc):
        rs = ctx.rt.nested_run(Code(ctx.code + 110), name="foo")

        # sub run
        assert rs.cycles == 440
        assert rs.nesting == 1
        assert rs.exit
        assert rs.pc == ctx.mach.get_run_exit_addr() + 2

    addr = ctx.mach.setup_quick_trap(func)
    addr2 = ctx.mach.setup_quick_trap(func2)

    # first code
    for i in range(0, 100, 2):
        ctx.mem.w16(ctx.code + i, op_nop)
    ctx.mem.w16(ctx.code + 100, op_jsr)
    ctx.mem.w32(ctx.code + 102, addr)
    ctx.mem.w16(ctx.code + 106, op_rts)

    # second code
    for i in range(110, 300, 2):
        ctx.mem.w16(ctx.code + i, op_nop)
    ctx.mem.w16(ctx.code + 300, op_jsr)
    ctx.mem.w32(ctx.code + 302, addr2)
    ctx.mem.w16(ctx.code + 306, op_rts)

    # start
    rs = ctx.rt.start(Code(ctx.code, ctx.stack), name="go")

    # main run results
    assert rs.cycles == 260
    assert rs.nesting == 0
    assert rs.exit
    assert rs.pc == ctx.mach.get_run_exit_addr() + 2

    ctx.cleanup()

    # check cycle reports
    assert len(slice_reports) > 0
    for run_state in slice_reports:
        if not run_state.exit:
            assert run_state.slice_cycles >= slice_cycles
