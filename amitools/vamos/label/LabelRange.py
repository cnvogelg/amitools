from amitools.vamos.Log import log_mem
import logging

class LabelRange:

  trace_val_str = ( "%02x      ", "%04x    ", "%08x" )

  def __init__(self, name, addr, size):
    self.name = name
    self.addr = addr
    self.size = size
    self.end  = addr + size
    self.next = None
    self.prev = None

  def trace_mem_int(self, mode, width, addr, value, text="", level=logging.DEBUG, addon=""):
    val = self.trace_val_str[width] % value
    log_mem.log(level, "%s(%d): %06x: %s  %6s  [@%06x +%06x %s] %s", mode, 2**width, addr, val, text, self.addr, addr - self.addr, self.name, addon)

  def trace_mem(self, mode, width, addr, value):
    self.trace_mem_int(mode, width, addr, value)
    return True

  def trace_block(self, mode, addr, size, text="", level=logging.DEBUG, addon=""):
    log_mem.log(level, "%s(B): %06x: +%06x   %6s  [@%06x +%06x %s] %s", mode, addr, size, text, self.addr, addr - self.addr, self.name, addon)

  def __str__(self):
    return "<@%06x +%06x %06x> [%s]" % (self.addr, self.size, self.addr + self.size, self.name)

  def is_inside(self, addr):
    return ((self.addr <= addr) and (addr < self.end))

  def does_intersect(self, addr, size):
    self_end = self.addr + self.size
    end = addr + size
    f1 = (end >= self.addr)
    f2 = (self_end >= addr)
    return f1 and f2

  def get_symbol(self, addr):
    return None

  def get_src_info(self, addr):
    return None
