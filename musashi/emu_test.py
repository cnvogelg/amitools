# emu_test.py
# test the musashi binding

from . import emu
from . import m68k


def run():
    print("create CPU, Memory, Traps")
    # 68k with 128 KiB mem
    cpu = emu.CPU(m68k.M68K_CPU_TYPE_68000)
    memory = emu.Memory(128)
    traps = emu.Traps()

    # get a special range
    spec_addr = memory.reserve_special_range()
    print("special range: %06x" % spec_addr)

    def invalid(mode, width, addr):
        print("MY INVALID: %s(%d): %06x" % (chr(mode), width, addr))

    def trace(mode, width, addr, value):
        print("TRACE: %s(%d): %06x: %x" % (chr(mode), width, addr, value))
        return 0

    memory.set_invalid_func(invalid)
    memory.set_trace_func(trace)
    memory.set_trace_mode(True)

    def pc_changed(addr):
        print("pc %06x" % (addr))

    def reset_handler():
        print("RESET")

    def instr_hook():
        print("INSTR HOOK")

    cpu.set_pc_changed_callback(pc_changed)
    cpu.set_reset_instr_callback(reset_handler)
    cpu.set_instr_hook_callback(instr_hook)

    print("resetting cpu...")
    cpu.pulse_reset()

    # write mem
    print("write mem...")
    memory.w16(0x1000, 0x4E70)  # RESET
    val = memory.r16(0x1000)
    print("RESET op=%04x" % val)

    # block write
    print(memory.r_block(0, 4))
    memory.w_block(0, "woah")
    print(memory.r_block(0, 4))

    # string
    memory.clear_block(0, 100, 11)
    memory.w_cstr(0, "hello, world!")
    s = memory.r_cstr(0)
    print(s, type(s))

    # string
    memory.clear_block(0, 100, 11)
    memory.w_bstr(0, "hello, world!")
    s = memory.r_bstr(0)
    print(s, type(s))

    # copy block
    memory.w_bstr(0, "hello, world!")
    memory.copy_block(0, 100, 100)
    txt = memory.r_bstr(100)
    print(txt)

    # valid range
    print("executing...")
    cpu.w_reg(m68k.M68K_REG_PC, 0x1000)
    print(cpu.execute(2))

    # invalid range
    print("executing invalid...")
    cpu.w_reg(m68k.M68K_REG_PC, spec_addr)
    print(cpu.execute(2))

    # test traps
    print("--- traps ---")

    def my_trap(op, pc):
        print("MY TRAP: %04x @ %08x" % (op, pc))

    tid = traps.setup(my_trap, auto_rts=True)
    print("trap id=", tid)

    # call trap
    memory.w16(0x2000, 0xA000 + tid)
    cpu.w_reg(m68k.M68K_REG_PC, 0x2000)
    print("call trap")
    print(cpu.execute(4))

    # free trap
    traps.free(tid)

    # special read
    print("special read...")

    def my_r16(addr):
        print("MY RANGE: %06x" % addr)
        return 0xDEAD

    memory.set_special_range_read_func(spec_addr, 1, my_r16)
    v = memory.r16(spec_addr)
    print("special=%0x" % v)

    # check if mem is in end mode?
    is_end = memory.is_end()
    print("mem is_end:", is_end)

    print("get/set register")
    print("%08x" % cpu.r_reg(m68k.M68K_REG_D0))
    cpu.w_reg(m68k.M68K_REG_D0, 0xDEADBEEF)
    print("%08x" % cpu.r_reg(m68k.M68K_REG_D0))

    # disassemble
    print("disassemble")
    print(cpu.disassemble(0x1000))

    print("done")


if __name__ == "__main__":
    run()
