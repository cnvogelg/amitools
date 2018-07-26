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
