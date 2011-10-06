from Exceptions import InvalidMemoryAccessError

class MemoryRange:
  
  trace_val_str = ( "%02x      ", "%04x    ", "%08x" )
  trace_levels = ( 'off','out','struct','trap','all' )
  
  TRACE_LEVEL_ALL = 4
  TRACE_LEVEL_TRAP = 3
  TRACE_LEVEL_STRUCT = 2
  TRACE_LEVEL_OUT = 1
  TRACE_LEVEL_OFF = 0
  
  def __init__(self, name, addr, size):
    self.name = name
    self.addr = addr
    self.size = size
    self.end = addr + size
    self.trace_level = 0
    self.trace_level_name = 'off'
  
  def set_trace(self, name):
    num = 0
    for f in self.trace_levels:
      if f == name:
        break
      num +=1
    self.trace_level = num
    self.trace_level_name = name
  
  def get_trace(self):
    return self.trace_level_name
    
  def set_trace_level(self, level):
    self.trace_level = level
    self.trace_level_name = self.trace_levels[level]
  
  def get_trace_level(self):
    return self.trace_level

  def trace_read(self, level, width, addr, value, text=""):
    if level <= self.trace_level:
      val = self.trace_val_str[width] % value
      print "R(%d): %06x: %s  %6s  [%s]" % (2**width, addr, val, text, self.name)
    
  def trace_write(self, level, width, addr, value, text=""):
    if level <= self.trace_level:
      val = self.trace_val_str[width] % value
      print "W(%d): %06x: %s  %6s  [%s]" % (2**width, addr, val, text, self.name)

  def __str__(self):
    return "<@%06x +%06x %06x> [%s]" % (self.addr, self.size, self.addr + self.size, self.name)
  
  def is_inside(self, addr):
    return ((self.addr <= addr) and (addr < self.end))
  
  def read_mem(self, width, addr):
    raise InvalidMemoryAccessError(width, addr)
  
  def write_mem(self, width, addr, val):
    raise InvalidMemoryAccessError(width, addr)
    
  def w_data(self, data, offset):
    raise InvalidMemoryAccessError(width, addr)

  def r_data(self, offset, size):
    raise InvalidMemoryAccessError(width, addr)

  def r_cstr(self, offset):
    raise InvalidMemoryAccessError(width, addr)
    
  def w_cstr(self, offset, cstr):
    raise InvalidMemoryAccessErrro(width, addr)

  def r_bstr(self, offset):
    raise InvalidMemoryAccessError(width, addr)

  def w_bstr(self, offset, bstr):
    raise InvalidMemoryAccessErrro(width, addr)
    