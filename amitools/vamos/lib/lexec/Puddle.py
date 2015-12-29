from amitools.vamos.Log import log_exec
from amitools.vamos.Exceptions import *

class Chunk:
  def __init__(self,base,size):
    self.base = base
    self.size = size

  def __str__(self):
    return "[0x%06x,0x%06x]" % (self.base,self.base + self.size)
    
class Puddle:
  def __init__(self, mem, alloc, label_mgr, name, size):
    self.alloc     = alloc;
    self.chunks    = None
    self.label_mgr = label_mgr
    self.mem       = mem
    self.raw_mem   = self.alloc.alloc_memory(name, size)
    self.low_addr  = self.raw_mem.addr
    self.hi_addr   = self.raw_mem.addr + size
    self.size      = size
    self.chunks    = []
    chunk          = Chunk(self.low_addr,size)
    self.chunks.append(chunk)

  def __str__(self):
    chunkstr = ""
    for chunk in self.chunks:
      if chunkstr == "":
        chunkstr = "%s" % chunk
      else:
        chunkstr = "%s,%s" % (chunkstr,chunk)
    return "[0x%06x,0x%06x] : %s" % (self.low_addr,self.hi_addr,chunkstr)

  def __del__(self):
    self.alloc.free_memory(self.raw_mem)
    del self.chunks

  def _find_best_fit(self, size):
    fit   = None
    delta = self.size << 1
    for chunk in self.chunks:
      if chunk.size == size:
        self.chunks.remove(chunk)
        result = chunk.base
        del chunk
        return result
      elif chunk.size > size:
        frag = chunk.size - (size << 1)
        if frag < 0:
          frag = -frag
        if frag < delta:
          fit   = chunk
          delta = frag
    if fit != None:
      result = chunk.base
      chunk.base += size
      chunk.size -= size
      return result
    return None

  def _add_chunk(self,base,size):
    for chunk in self.chunks:
      if base + size == chunk.base:
        self.chunks.remove(chunk)
        self._add_chunk(base,size + chunk.size)
        del chunk
        return
      elif chunk.base + chunk.size == base:
        self.chunks.remove(chunk)
        self._add_chunk(chunk.base,size + chunk.size)
        del chunk
        return
    self.chunks.insert(0,Chunk(base,size))
    
  def AllocPooled(self, name, size):
    base = self._find_best_fit(size)
    if base != None:
      self.mem.access.clear_data(base ,size , 0)
      return base
    else:
      return 0

  def FreePooled(self, addr, size):
    self._add_chunk(addr, size)

  def contains(self, addr, size):
    if addr >= self.low_addr and addr + size <= self.hi_addr:
      return True
    return False
