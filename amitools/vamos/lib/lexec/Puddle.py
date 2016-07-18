from amitools.vamos.Log import log_exec
from amitools.vamos.Exceptions import *
from amitools.vamos.MemoryAlloc import *

class Puddle:
  def __init__(self, mem, alloc, label_mgr, name, size):
    self.alloc     = alloc;
    self.chunks    = None
    self.label_mgr = label_mgr
    self.mem       = mem
    self.raw_size  = size
    self.raw_mem   = self.alloc.alloc_memory(name, size)
    self.chunks    = MemoryAlloc(self.mem, self.raw_mem.addr, size, self.raw_mem.addr, label_mgr)

  def __del__(self):
    if self.raw_mem != None:
      self.label_mgr.delete_labels_within(self.raw_mem.addr,self.raw_size)
      self.chunks = None
      self.alloc.free_memory(self.raw_mem)
      self.raw_mem = None

  def AllocPooled(self, name, size):
    return self.chunks.alloc_memory(name,size,True,False)

  def FreePooled(self, addr, size):
    mem = self.chunks.get_memory(addr)
    if mem != None:
      if mem.size == size:
        self.chunks.free_memory(mem)
      else:
        raise VamosInternalError("release size %d for memory chunk %s != reserved size %s" % (size,mem,mem.size))
    else:
      raise VamosInternalError("memory at 0x%0x not recorded in puddle" % addr)

  def contains(self, addr, size):
    if self.chunks.is_valid_address(addr):
      return True
    return False
