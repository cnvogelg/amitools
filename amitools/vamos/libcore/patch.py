
class LibPatcherMultiTrap(object):
  """patch in a stub by adding traps for each call"""

  def __init__(self, mem, traps, stub):
    self.mem = mem
    self.traps = traps
    self.stub = stub
    self.tids = []

  def patch_jump_table(self, base_addr):
    """patch the stub into the jump table for the lib at base_addr"""
    addr = base_addr - 6
    func_table = self.stub.get_func_tab()
    for func in func_table:
      # setup new patch
      tid = self.traps.setup(func, auto_rts=True)
      if tid < 0:
        raise RuntimeError("no more traps available!")
      # generate opcode
      op = 0xa000 | tid
      # write trap
      self.mem.w16(addr, op)
      self.mem.w32(addr + 2, 0)
      # remember trap
      self.tids.append(tid)
      # next slot
      addr -= 6

  def cleanup(self):
    """remove traps"""
    for tid in self.tids:
      self.traps.free(tid)
    self.tids = []
