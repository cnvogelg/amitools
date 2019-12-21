from amitools.vamos.machine import DisAsm, Machine


def machine_disasm_default_test():
  mach = Machine()
  disasm = DisAsm(mach)
  mem = mach.get_mem()
  cpu = mach.get_cpu()
  traps = mach.get_traps()
  # trap without func
  mem.w16(0, 0xa123)
  assert disasm.disassemble(0) == (2, "PyTrap  #$123")
  # trap with func
  def bla(opcode, pc):
    pass
  tid = traps.setup(bla)
  mem.w16(2, 0xa000 | tid)
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
