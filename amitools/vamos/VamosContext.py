class VamosContext:
  def __init__(self, cpu, mem, lib_mgr, alloc):
    self.cpu = cpu
    self.mem = mem
    self.lib_mgr = lib_mgr
    self.alloc = alloc
