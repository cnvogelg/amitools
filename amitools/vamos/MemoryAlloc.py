from MemoryLayout import MemoryLayout
from MemoryBlock import MemoryBlock
from MemoryStruct import MemoryStruct
from Exceptions import OutOfAmigaMemoryError

class MemoryAlloc(MemoryLayout):
  
  def __init__(self, name, addr, size):
    MemoryLayout.__init__(self, name, addr, size)
    self._cur = addr
    self.addrs = {}
  
  def alloc_range(self, size, padding):
    addr = self._cur
    addr = (addr + padding - 1) & ~(padding - 1)
    self._cur = addr + size
    if (self._cur - self.addr) > self.size:
      raise OutOfAmigaMemoryError(self, size)
    print "\t[alloc @%06x: %06x bytes (padding %x)]" % (addr,size,padding)
    return addr
  
  def free_range(self, addr, size):
    # TODO real free
    print "\t[free  @%06x: %06x bytes]" % (addr,size)

  def _reg_range(self, addr, obj):
    self.addrs[addr] = obj

  def _unreg_range(self, addr):
    del self.addrs[addr]

  def get_range_by_addr(self, addr):
    if self.addrs.has_key(addr):
      return self.addrs[addr]
    else:
      return None
      
  # ----- convenience functions -----
  
  def alloc_memory(self, name, size, padding=4):
    addr = self.alloc_range(size, padding)
    mb = MemoryBlock(name, addr, size)
    mb.set_trace_level(self.get_trace_level())
    self.add_range(mb)
    self._reg_range(addr, mb)
    return mb
  
  def free_memory(self, mb):
    self.free_range(mb.addr, mb.size)
    self.remove_range(mb)
    self._unreg_range(mb.addr)
  
  def alloc_struct(self, name, struct, padding=4):
    addr = self.alloc_range(struct.get_size(), padding)
    ms = MemoryStruct(name, addr, struct)
    ms.set_trace_level(self.get_trace_level())
    self.add_range(ms)
    self._reg_range(addr, ms)
    return ms
  
  def free_struct(self, ms):
    self.free_range(ms.addr, ms.size)
    self.remove_range(ms)
    self._unreg_range(addr)
  
  
  
  