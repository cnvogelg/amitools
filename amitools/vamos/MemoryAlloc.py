from MemoryLayout import MemoryLayout
from MemoryBlock import MemoryBlock
from MemoryStruct import MemoryStruct
from Exceptions import OutOfAmigaMemoryError

from Log import log_mem_alloc

class MemoryAlloc(MemoryLayout):
  
  def __init__(self, name, addr, size):
    MemoryLayout.__init__(self, name, addr, size)
    self._cur = addr
    self.addrs = {}
  
  def alloc_range(self, size, padding=4):
    addr = self._cur
    addr = (addr + padding - 1) & ~(padding - 1)
    self._cur = addr + size
    if (self._cur - self.addr) > self.size:
      raise OutOfAmigaMemoryError(self, size)
    log_mem_alloc.info("[alloc @%06x: %06x bytes (padding %x)]", addr,size,padding)
    return addr
  
  def free_range(self, addr, size):
    # TODO real free
    log_mem_alloc.info("[free  @%06x: %06x bytes]", addr, size)

  def reg_range(self, addr, obj):
    self.addrs[addr] = obj
    self.add_range(obj)

  def unreg_range(self, addr):
    obj = self.addrs[addr]
    del self.addrs[addr]
    self.remove_range(obj)

  def get_range_by_addr(self, addr):
    if self.addrs.has_key(addr):
      return self.addrs[addr]
    else:
      return None
      
  # ----- convenience functions -----
  
  def alloc_memory(self, name, size, padding=4):
    addr = self.alloc_range(size, padding)
    mb = MemoryBlock(name, addr, size)
    self.reg_range(addr, mb)
    log_mem_alloc.info(mb)
    return mb
  
  def free_memory(self, mb):
    self.unreg_range(mb.addr)
    self.free_range(mb.addr, mb.size)
  
  def alloc_struct(self, name, struct, padding=4):
    addr = self.alloc_range(struct.get_size(), padding)
    ms = MemoryStruct(name, addr, struct)
    self.reg_range(addr, ms)
    log_mem_alloc.info(ms)
    return ms
  
  def free_struct(self, ms):
    self.unreg_range(addr)
    self.free_range(ms.addr, ms.size)
  
  def alloc_cstr(self, name, cstr, padding=4):
    size = len(cstr) + 1
    mb = self.alloc_memory(name, size, padding)
    mb.w_cstr(mb.addr, cstr)
    return mb
  
  def alloc_bstr(self, name, bstr, padding=4):
    size = len(bstr) + 1
    mb = self.alloc_memory(name, size, padding)
    mb.w_bstr(mb.addr, bstr)
    return mb

  
  
  