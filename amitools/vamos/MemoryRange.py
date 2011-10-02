from Exceptions import InvalidMemoryAccessError

class MemoryRange:
  
  def __init__(self, name, addr, size):
    self.name = name
    self.addr = addr
    self.size = size
    self.end = addr + size
  
  def __str__(self):
    return "[%s] addr=%06x size=%06x" % (self.name, self.addr, self.size)
  
  def is_inside(self, addr):
    return ((self.addr <= addr) and (addr < self.end))
  
  def read_mem(self, width, addr):
    raise InvalidMemoryAccessError(width, addr)
  
  def write_mem(self, width, addr, val):
    raise InvalidMemoryAccessError(width, addr)
    
  def write_data(self, data, offset):
    raise InvalidMemoryAccessError(width, addr)

  def read_data(self, offset, size):
    raise InvalidMemoryAccessError(width, addr)

  def read_cstring(self, offset):
    raise InvalidMemoryAccessError(width, addr)
    