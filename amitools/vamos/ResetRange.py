from MemoryBlock import MemoryBlock

class ResetRange(MemoryBlock):
  def __init__(self, first_pc, initial_stack):
    MemoryBlock.__init__(self, "reset", 0, 8)
    self.w32(4, first_pc)
    self.w32(0, initial_stack)