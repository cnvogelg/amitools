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
  
  def trace_read(self, width, addr, value, text="", level=logging.DEBUG, addon=""):
    val = self.trace_val_str[width] % value
    log_mem.log(level, "R(%d): %06x: %s  %6s  [@%06x +%06x %s] %s", 2**width, addr, val, text, self.addr, addr - self.addr, self.name, addon)
    
  def trace_write(self, width, addr, value, text="", level=logging.DEBUG, addon=""):
    val = self.trace_val_str[width] % value
    log_mem.log(level, "W(%d): %06x: %s  %6s  [@%06x +%06x %s] %s", 2**width, addr, val, text, self.addr, addr - self.addr, self.name, addon)

  def __str__(self):
    return "<@%06x +%06x %06x> [%s]" % (self.addr, self.size, self.addr + self.size, self.name)
  
  def is_inside(self, addr):
    return ((self.addr <= addr) and (addr < self.end))
  
  def r8(self, addr):
    return self.read_mem(0, addr)

  def r16(self, addr):
    return self.read_mem(1, addr)

  def r32(self, addr):
    return self.read_mem(2, addr)

  def w8(self, addr, v):
    self.write_mem(0, addr, v)

  def w16(self, addr, v):
    self.write_mem(1, addr, v)

  def w32(self, addr, v):
    self.write_mem(2, addr, v)
  
  def read_mem(self, width, addr):
    raise InvalidMemoryAccessError('R', width, addr, self.name)
  
  def write_mem(self, width, addr, val):
    raise InvalidMemoryAccessError('W', width, addr, self.name)
    
  def r_data(self, offset, size):
    raise InvalidMemoryAccessError('R', 0, addr, self.name)

  def w_data(self, data, offset):
    raise InvalidMemoryAccessError('W', 0, addr, self.name)

  def r_cstr(self, offset):
    raise InvalidMemoryAccessError('R', 0, addr, self.name)
    
  def w_cstr(self, offset, cstr):
    raise InvalidMemoryAccessErrro('W', 0, addr, self.name)

  def r_bstr(self, offset):
    raise InvalidMemoryAccessError('R', 0, addr, self.name)

  def w_bstr(self, offset, bstr):
    raise InvalidMemoryAccessErrro('W', 0, addr, self.name)
    