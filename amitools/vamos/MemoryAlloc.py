from MemoryLayout import MemoryLayout
from MemoryBlock import MemoryBlock

class MemoryAlloc(MemoryLayout):
  
  def __init__(self, name, addr, size, verbose=True):
    MemoryLayout.__init__(self, name, addr, size, verbose)
    self._cur = addr
  
  def allocRange(self, size, padding):
    addr = self._cur
    addr = (addr + padding - 1) & ~(padding - 1)
    self._cur = addr + size
    if self._cur - self.addr > size:
      raise OutOfAmigaMemory(self)
    print "\t[alloc @%06x: %06x bytes (padding %x)]" % (addr,size,padding)
    return addr
  
  def freeRange(self, addr, size):
    # TODO real free
    print "\t[free  @%06x: %06x bytes]" % (addr,size)
  
  # ----- convenience functions -----
  
  def allocMemory(self, name, size, padding=4):
    addr = self.allocRange(size, padding)
    mb = MemoryBlock(name, addr, size)
    self.add_range(mb)
    return mb
  
  def freeMemory(self, mb):
    self.freeRange(mb.addr, mb.size)
    self.remove_range(mb)
  
  def allocStruct(self, name, struct, padding=4):
    addr = self.allocRange(struct.get_size(), padding)
    ms = MemoryStruct(name, addr, struct)
    self.add_range(ms)
    return ms
  
  def freeStruct(self, ms):
    self.freeRange(ms.addr, ms.size)
    self.remove_range(ms)
  
  
  
  