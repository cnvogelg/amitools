from Exceptions import OutOfAmigaMemoryError
from Log import log_mem_alloc
from LabelRange import LabelRange
from LabelStruct import LabelStruct
from AccessStruct import AccessStruct

class Memory:
  def __init__(self, addr, size, label, access):
    self.addr = addr
    self.size = size
    self.label = label
    self.access = access
  def __str__(self):
    return str(self.label)

class MemoryAlloc:
  
  def __init__(self, mem, addr, size, begin, label_mgr):
    if begin == 0:
      self._cur = addr
    else:
      self._cur = begin
    self.addr = addr
    self.size = size
    self.addrs = {}
    self.mem = mem
    self.access = mem.access
    self.label_mgr = label_mgr
  
  # return addr
  def alloc_mem(self, size, padding=4):
    addr = self._cur
    addr = (addr + padding - 1) & ~(padding - 1)
    self._cur = addr + size
    if (self._cur - self.addr) > self.size:
      raise OutOfAmigaMemoryError(self, size)
    log_mem_alloc.info("[alloc @%06x: %06x bytes (padding %x)]", addr,size,padding)
    self.addrs[addr] = size
    return addr
  
  def free_mem(self, addr, size):
    # TODO real free
    log_mem_alloc.info("[free  @%06x: %06x bytes]", addr, size)
    del self.addrs[addr]

  def get_range_by_addr(self, addr):
    if self.addrs.has_key(addr):
      return self.addrs[addr]
    else:
      return None
      
  # ----- convenience functions with label creation -----
  
  # memory
  def alloc_memory(self, name, size, padding=4):
    addr = self.alloc_mem(size, padding)
    label = LabelRange(name, addr, size)
    self.label_mgr.add_label(label)
    return Memory(addr,size,label,self.mem.access)
  
  def free_memory(self, mem):
    self.label_mgr.remove_label(mem.label)
    self.free_mem(mem.addr, mem.size)
  
  # struct
  def alloc_struct(self, name, struct, padding=4):
    size = struct.get_size()
    addr = self.alloc_mem(size, padding)
    label = LabelStruct(name, addr, struct)
    self.label_mgr.add_label(label)
    access = AccessStruct(self.mem, self.label_mgr, struct, addr)
    return Memory(addr,size,label,access)
  
  def free_struct(self, mem):
    self.label_mgr.remove_label(mem.label)
    self.free_mem(mem.addr, mem.size)
  
  # cstr
  def alloc_cstr(self, name, cstr, padding=4):
    size = len(cstr) + 1
    addr = self.alloc_mem(size, padding)
    label = LabelRange(name, addr, size)
    self.label_mgr.add_label(label)
    self.mem.access.w_cstr(addr, cstr)
    return Memory(addr,size,label,self.mem.access)
  
  def free_cstr(self, mem):
    self.label_mgr.remove_label(mem.label)
    self.free_mem(mem.addr, mem.size)    
  
  # bstr
  def alloc_bstr(self, name, bstr, padding=4):
    size = len(bstr) + 1
    addr = self.alloc_mem(size, padding)
    label = LabelRange(name, addr, size)
    self.label_mgr.add_label(label)
    self.mem.access.w_bstr(addr, bstr)
    return Memory(addr,size,label,self.mem.access)
  
  def free_bstr(self, mem):
    self.label_mgr.remove_label(mem.label)
    self.free_mem(mem.addr, mem.size)    

  
  
  