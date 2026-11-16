from types import SimpleNamespace

import pytest

from amitools.vamos.lib.lexec.supervisor import run_supervisor
from amitools.vamos.machine import REG_A5, REG_D0, Code, Machine, Runtime
from amitools.vamos.machine.backend import Machine68kBackend
from amitools.vamos.mem import MemoryAlloc


@pytest.mark.parametrize("cpu_name", ["68000", "68020"])
@pytest.mark.parametrize("supervisor", [False, True])
def exec_supervisor_rte_test(cpu_name, supervisor):
    machine = Machine(
        Machine68kBackend().create_machine(cpu_name), supervisor=supervisor
    )
    runtime = Runtime(machine)
    alloc = MemoryAlloc.for_machine(machine)
    ctx = SimpleNamespace(
        machine=machine,
        cpu=machine.cpu,
        mem=machine.mem,
        alloc=alloc,
        cpu_name=cpu_name,
        runner=runtime.run,
    )
    code = alloc.alloc_memory(32)
    callback = code.addr + 16
    machine.mem.w_block(callback, bytes.fromhex("702a4e73"))  # moveq #42,d0; rte
    seen = []

    def call(opcode, address):
        before = (ctx.cpu.r_sr(), ctx.cpu.r_sp(), ctx.cpu.r_isp(), ctx.cpu.r_msp())
        assert run_supervisor(ctx) == 42
        assert (
            ctx.cpu.r_sr(),
            ctx.cpu.r_sp(),
            ctx.cpu.r_isp(),
            ctx.cpu.r_msp(),
        ) == before
        seen.append(True)

    trap = machine.setup_quick_trap(call)
    machine.mem.w16(code.addr, 0x4EB9)
    machine.mem.w32(code.addr + 2, trap)
    machine.mem.w16(code.addr + 6, 0x4E75)
    try:
        result = runtime.run(
            Code(code.addr, machine.get_scratch_top(), {REG_A5: callback}, [REG_D0])
        )
        assert result.exit and result.mach_error is None
        assert result.regs[REG_D0] == 42
        assert seen == [True]
    finally:
        alloc.free_memory(code)
        assert alloc.is_all_free()
        machine.cleanup()


def exec_supervisor_control_register_persists_test():
    machine = Machine(Machine68kBackend().create_machine("68020"))
    runtime = Runtime(machine)
    alloc = MemoryAlloc.for_machine(machine)
    ctx = SimpleNamespace(
        machine=machine,
        cpu=machine.cpu,
        mem=machine.mem,
        alloc=alloc,
        cpu_name="68020",
        runner=runtime.run,
    )
    code = alloc.alloc_memory(32)
    # Freeze the 68020 instruction cache, return, then read CACR again.
    machine.mem.w_block(code.addr + 16, bytes.fromhex("70024e7b00024e73"))
    machine.mem.w_block(code.addr + 24, bytes.fromhex("4e7a00024e73"))

    def call(opcode, address):
        ctx.cpu.w_reg(REG_A5, code.addr + 16)
        run_supervisor(ctx)
        ctx.cpu.w_reg(REG_A5, code.addr + 24)
        assert run_supervisor(ctx) == 2

    trap = machine.setup_quick_trap(call)
    machine.mem.w16(code.addr, 0x4EB9)
    machine.mem.w32(code.addr + 2, trap)
    machine.mem.w16(code.addr + 6, 0x4E75)
    try:
        result = runtime.run(Code(code.addr, machine.get_scratch_top()))
        assert result.exit and result.mach_error is None
    finally:
        alloc.free_memory(code)
        assert alloc.is_all_free()
        machine.cleanup()
