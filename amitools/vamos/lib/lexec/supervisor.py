"""Run an Exec Supervisor callback with a real 68k RTE frame."""

import struct
from contextlib import ExitStack

from amitools.vamos.machine import REG_D0, Code


def run_supervisor(ctx):
    cpu = ctx.cpu
    original = cpu.get_cpu_context()
    pc, sp, sr = cpu.r_pc(), cpu.r_sp(), cpu.r_sr()
    isp, msp = cpu.r_isp(), cpu.r_msp()
    finished = []

    def capture(opcode, address):
        # Runtime restores its saved CPU context after a nested call. Keep
        # the callback's control-register writes (CACR, VBR, etc.) as well
        # as its general registers, rather than discarding them on return.
        finished.append(cpu.get_cpu_context())

    with ExitStack() as cleanup:
        memory = ctx.alloc.alloc_memory(8192 + 32, label="Exec Supervisor frame")
        cleanup.callback(ctx.alloc.free_memory, memory)
        trap = ctx.machine.get_traps().alloc(capture)
        cleanup.callback(ctx.machine.get_traps().free, trap)
        start = memory.addr + 8192
        prefix = b"" if ctx.cpu_name == "68000" else bytes.fromhex("4267")
        return_pc = start + len(prefix) + 12
        # [format/vector], return PC, saved SR; jump to the function in A5.
        # The callback's RTE lands on the capture trap, then RTS returns to
        # Runtime. The outer caller's original SR and stacks are restored
        # below, keeping temporary supervisor storage separate from its USP.
        program = prefix + struct.pack(
            ">HIHHHHH",
            0x2F3C,
            return_pc,
            0x3F3C,
            (sr | 0x2000) & 0x3FFF,
            0x4ED5,
            0xA000 | trap,
            0x4E75,
        )
        ctx.mem.w_block(start, program)
        try:
            cpu.w_sr((sr | 0x2000) & 0x3FFF)
            result = ctx.runner(Code(start, sp=start), name="Exec Supervisor")
            if result.mach_error:
                raise result.mach_error
            if not finished:
                raise RuntimeError("Supervisor callback did not return with RTE")
        except BaseException:
            cpu.set_cpu_context(original)
            raise
        cpu.set_cpu_context(finished[-1])
        cpu.w_sr(sr)
        cpu.w_isp(isp)
        cpu.w_msp(msp)
        cpu.w_sp(sp)
        cpu.w_pc(pc)
        return cpu.r_reg(REG_D0)
