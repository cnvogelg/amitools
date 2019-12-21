class DisAsm(object):
  def __init__(self, machine):
    self.machine = machine
    self.cpu = machine.get_cpu()
    self.traps = machine.get_traps()

  def disassemble(self, pc):
    num_bytes, txt = self.cpu.disassemble(pc)
    # trap?
    if txt.startswith('dc.w    $a'):
      tid = int(txt[10:13], 16)
      txt = self._parse_trap(tid)
    return num_bytes, txt

  def disassemble_raw(self, pc, data):
    num_bytes, txt = self.cpu.disassemble_raw(pc, data)
    return num_bytes, txt

  def _parse_trap(self, tid):
    func = self.traps.get_func(tid)
    if func:
      if hasattr(func, '__name__'):
        name = func.__name__
      else:
        name = str(func)
      return "PyTrap  #$%03x ; %s" % (tid, name)
    else:
      return "PyTrap  #$%03x" % tid

