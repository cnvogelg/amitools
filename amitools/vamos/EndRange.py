from MemoryBlock import MemoryBlock

class EndRange(MemoryBlock):
  def __init__(self, addr):
    MemoryBlock.__init__(self, "end", addr, 2)
    self.w16(addr, 0x4e70) # RESET opcode
