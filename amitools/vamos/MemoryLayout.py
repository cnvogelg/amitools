from MemoryRange import MemoryRange
from Exceptions import InvalidMemoryAccessError

MEMORY_WIDTH_BYTE = 0
MEMORY_WIDTH_WORD = 1
MEMORY_WIDTH_LONG = 2

class MemoryLayout(MemoryRange):
  
  def __init__(self, name, addr, size):
    MemoryRange.__init__(self, name, addr, size)
    self.ranges = []
  
  def set_trace(self, on):
    MemoryRange.set_trace(self, on)
    for r in self.ranges:
      r.set_trace(on)
  
  def add_range(self, range):
    self.ranges.append(range)
  
  def remove_range(self, range):
    self.ranges.remove(range)
  
  def get_all_ranges(self):
    return self.ranges[:]
  
  def get_range(self, addr):
    for r in self.ranges:
      if r.is_inside(addr):
        return r
    return None

  def read_mem(self, width, addr):
    r = self.get_range(addr)
    if r != None:
      val = r.read_mem(width, addr)
      return val
    else:
      raise InvalidMemoryAccessError(width, addr)
  
  def write_mem(self, width, addr, val):
    r = self.get_range(addr)
    if r != None:
      r.write_mem(width, addr, val)
      return None
    else:
      raise InvalidMemoryAccessError(width, addr)
    
  def set_data(self, addr, data):
    r = self.get_range(addr)
    if r != None:
      r.set_data(addr, data)
    else:
      raise InvalidMemoryAccessError(0, addr)

  def get_data(self, addr, size):
    r = self.get_range(addr)
    if r != None:
      return r.get_data(addr, size)
    else:
      raise InvalidMemoryAccessError(0, addr)

  def get_cstring(self, addr):
    r = self.get_range(addr)
    if r != None:
      return r.get_cstring(addr)
    else:
      raise InvalidMemoryAccessError(0, addr)
