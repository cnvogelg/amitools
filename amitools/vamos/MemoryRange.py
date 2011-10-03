from Exceptions import InvalidMemoryAccessError

class MemoryRange:
  
  trace_val_str = ( "%02x      ", "%04x    ", "%08x" )
  
  def __init__(self, name, addr, size):
    self.name = name
    self.addr = addr
    self.size = size
    self.end = addr + size
    self.trace = False
  
  def set_trace(self, on):
    self.trace = True
    
  def trace_read(self, width, addr, value, text=""):
    if self.trace:
      val = self.trace_val_str[width] % value
      print "R(%d): %06x: %s %4s [%s]" % (2**width, addr, val, text, self.name)
    
  def trace_write(self, width, addr, value, text=""):
    if self.trace:
      val = self.trace_val_str[width] % value
      print "W(%d): %06x: %s %4s [%s]" % (2**width, addr, val, text, self.name)

  def __str__(self):
    return "<@%06x +%06x %06x> [%s]" % (self.addr, self.size, self.addr + self.size, self.name)
  
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
    