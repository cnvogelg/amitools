from MemoryBlock import MemoryBlock

class AmigaExecBase(MemoryBlock):
  
  def __init__(self, exec_base):
    MemoryBlock.__init__(self, "ExecBase", 4, 4)
    self.w32(4, exec_base)