from MemoryLayout import MemoryLayout
from Exceptions import InvalidMemoryAccessError

class MainMemory(MemoryLayout):
  
  def __init__(self, size):
    MemoryLayout.__init__(self, "main", 0, size)
    self.invalid_reads = []
    self.invalid_writes = []
    
  def get_read_funcs(self):
    return ( lambda addr: self.read_mem(0,addr),
             lambda addr: self.read_mem(1,addr),
             lambda addr: self.read_mem(2,addr))

  def get_write_funcs(self):
    return ( lambda addr,val: self.write_mem(0,addr,val),
             lambda addr,val: self.write_mem(1,addr,val),
             lambda addr,val: self.write_mem(2,addr,val))

  def read_mem(self, width, addr):
    try:
      return MemoryLayout.read_mem(self, width, addr)
    except InvalidMemoryAccessError as e:
      self.trace_read(e.width, e.addr, 0, text="OUT!");
      self.invalid_reads.append((e.width, e.addr))
      return 0

  def write_mem(self, width, addr, val):
    try:
      return MemoryLayout.write_mem(self, width, addr, val)
    except InvalidMemoryAccessError as e:
      self.trace_write(e.width, e.addr, 0, text="OUT!")
      self.invalid_writes.append((e.width, e.addr))
      return None
  