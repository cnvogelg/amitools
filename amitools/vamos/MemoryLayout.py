from MemoryRange import MemoryRange
from Exceptions import InvalidMemoryAccessError

MEMORY_WIDTH_BYTE = 0
MEMORY_WIDTH_WORD = 1
MEMORY_WIDTH_LONG = 2

class MemoryLayout(MemoryRange):
  
  def __init__(self, name, addr, size):
    MemoryRange.__init__(self, name, addr, size)
    self.ranges = []
  
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
    
  def w_data(self, addr, data):
    r = self.get_range(addr)
    if r != None:
      r.w_data(addr, data)
    else:
      raise InvalidMemoryAccessError(0, addr)

  def r_data(self, addr, size):
    r = self.get_range(addr)
    if r != None:
      return r.r_data(addr, size)
    else:
      raise InvalidMemoryAccessError(0, addr)

  def r_cstr(self, addr):
    r = self.get_range(addr)
    if r != None:
      return r.r_cstr(addr)
    else:
      raise InvalidMemoryAccessError(0, addr)

  def w_cstr(self, addr, cstr):
    r = self.get_range(addr)
    if r != None:
      r.w_cstr(addr, cstr)
    else:
      raise InvalidMemoryAccessError(0, addr)

  def r_bstr(self, addr):
    r = self.get_range(addr)
    if r != None:
      return r.r_bstr(addr)
    else:
      raise InvalidMemoryAccessError(0, addr)

  def w_bstr(self, addr, bstr):
    r = self.get_range(addr)
    if r != None:
      r.w_bstr(addr, bstr)
    else:
      raise InvalidMemoryAccessError(0, addr)
