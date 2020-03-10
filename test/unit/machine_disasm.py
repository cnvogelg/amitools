from amitools.vamos.machine import DisAsm, Machine


def machine_disasm_default_test():
    mach = Machine()
    disasm = DisAsm(mach)
    mem = mach.get_mem()
    cpu = mach.get_cpu()
    traps = mach.get_traps()
    # trap without func
    mem.w16(0, 0xA123)
    assert disasm.disassemble(0) == (2, "PyTrap  #$123")
    # trap with func

    def bla(opcode, pc):
        pass

    tid = traps.setup(bla)
    mem.w16(2, 0xA000 | tid)
    assert disasm.disassemble(2) == (2, "PyTrap  #$%03x ; bla" % tid)
    traps.free(tid)


def machine_disasm_raw_test():
    mach = Machine()
    disasm = DisAsm(mach)
    buf = b"\x4e\x75"
    assert disasm.disassemble_raw(0, buf) == (2, "rts")
    buf = b"\x10\x1c"
    assert disasm.disassemble_raw(0, buf) == (2, "move.b  (A4)+, D0")
    buf = b"\x48\xe7\x3f\x3e"
    assert disasm.disassemble_raw(0, buf) == (4, "movem.l D2-D7/A2-A6, -(A7)")
    # too short buffer
    buf = b"\x48\xe7"
    assert disasm.disassemble_raw(0, buf) == (0, "")


def machine_disasm_line_test():
    mach = Machine()
    disasm = DisAsm(mach)
    buf = b"\x4e\x75"
    assert disasm.disassemble_line(0x100, buf) == (0x100, [0x4E75], "rts")
    buf = b"\x10\x1c"
    assert disasm.disassemble_line(0x200, buf) == (0x200, [0x101C], "move.b  (A4)+, D0")
    buf = b"\x48\xe7\x3f\x3e"
    assert disasm.disassemble_line(0x300, buf) == (
        0x300,
        [0x48E7, 0x3F3E],
        "movem.l D2-D7/A2-A6, -(A7)",
    )
    # too short buffer
    buf = b"\x48\xe7"
    assert disasm.disassemble_line(0, buf) == (0, [], "")


def machine_disasm_block_test():
    mach = Machine()
    disasm = DisAsm(mach)
    buf = b"\x4e\x75" + b"\x10\x1c" + b"\x48\xe7\x3f\x3e"
    assert disasm.disassemble_block(buf, 0x100) == [
        (0x100, [0x4E75], "rts"),
        (0x102, [0x101C], "move.b  (A4)+, D0"),
        (0x104, [0x48E7, 0x3F3E], "movem.l D2-D7/A2-A6, -(A7)"),
    ]


def machine_disasm_block_dump_test():
    mach = Machine()
    disasm = DisAsm(mach)
    buf = b"\x4e\x75" + b"\x10\x1c" + b"\x48\xe7\x3f\x3e" + b"\x48\xe7"
    code = disasm.disassemble_block(buf, 0x100)
    result = []

    def store(line):
        result.append(line)

    disasm.dump_block(code, store)
    assert result == [
        "00000100:  4e75                  rts",
        "00000102:  101c                  move.b  (A4)+, D0",
        "00000104:  48e7 3f3e             movem.l D2-D7/A2-A6, -(A7)",
    ]


def machine_disasm_create_test():
    disasm = DisAsm.create()
    buf = b"\x4e\x75"
    assert disasm.disassemble_raw(0, buf) == (2, "rts")
    disasm = DisAsm.create("68020")
    buf = b"\x60\xff\x11\x22\x33\x44"
    assert disasm.disassemble_raw(0, buf) == (6, "bra     $11223346; (2+)")
