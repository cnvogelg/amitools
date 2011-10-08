from Exceptions import InvalidMemoryAccessError

from Log import log_mem
import logging

class MemoryRange:
  
  trace_val_str = ( "%02x      ", "%04x    ", "%08x" )
  
  def __init__(self, name, addr, size):
    self.name = name
    self.addr = addr
    self.size = size
    self.end = addr + size
  
  def trace_read(self, width, addr, value, text="", level=logging.DEBUG):
    val = self.trace_val_str[width] % value
    log_mem.log(level, "R(%d): %06x: %s  %6s  [%s]", 2**width, addr, val, text, self.name)
    
  def trace_write(self, width, addr, value, text="", level=logging.DEBUG):
    val = self.trace_val_str[width] % value
    log_mem.log(level, "W(%d): %06x: %s  %6s  [%s]", 2**width, addr, val, text, self.name)

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
    