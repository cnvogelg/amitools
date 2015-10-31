from amitools.vamos.Log import log_exec
from amitools.vamos.Exceptions import *

class Puddle:
  
  def __init__(self, alloc, name, size):
    
    self.alloc = alloc;
    self.bytesleft = 0;
    self.current = 0;
    mem = self.alloc.alloc_memory(name, size)
    if mem != None:
      self.mem = mem
      self.bytesleft = mem.size
      self.current = mem.addr

  def __del__(self):
    if self.mem != None:
      self.alloc.free_memory(self.mem)
      self.bytesleft = 0
      self.current = 0;
    
  def AllocPooled(self, name, size):
    result = 0;
    if (size <= self.bytesleft):
      result = self.current
      self.current+=size;
      self.bytesleft -= size;
    if (result != 0):
      log_exec.info("%s: %06x from pool at base %06x" % (name, result, self.mem.addr))
    return result
