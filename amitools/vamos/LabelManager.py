import logging
from Log import *

MEMORY_WIDTH_BYTE = 0
MEMORY_WIDTH_WORD = 1
MEMORY_WIDTH_LONG = 2

class LabelManager:
  trace_val_str = ( "%02x      ", "%04x    ", "%08x" )

  def __init__(self):
    self.ranges = []
    self.error_tracker = None # will be set later

  def add_label(self, range):
    self.ranges.append(range)

  def remove_label(self, range):
    if range in self.ranges:
      self.ranges.remove(range)
    else:
      # try to find compatible
      for r in self.ranges:
        if r.addr == range.addr and r.size == range.size:
          self.ranges.remove(r)
          log_mem_int.log(logging.WARN, "remove_label: got=%s have=%s", range, r)
          return
      log_mem_int.log(logging.ERROR, "remove_label: invalid range %s", range)

  def get_all_labels(self):
    return self.ranges[:]

  def dump(self):
    for r in self.ranges:
      print r

  def get_label(self, addr):
    for r in self.ranges:
      if r.is_inside(addr):
        return r
    return None

  def get_intersecting_labels(self, addr, size):
    result = []
    for r in self.ranges:
      if r.does_intersect(addr,size):
        result.append(r)
    return result

  def get_label_offset(self, addr):
    r = self.get_label(addr)
    if r == None:
      return (None, 0)
    else:
      off = addr - r.addr
      return (r, off)

  # trace callback from CPU core
  # mode is an integer with values 'R' and 'W' there
  def trace_mem(self, mode, width, addr, val):
    mode_char = chr(mode)
    r = self.get_label(addr)
    if r != None:
      ok = r.trace_mem(mode_char, width, addr, val)
      if ok:
        return 0
    self.error_tracker.report_invalid_memory(mode, width, addr)
    return 1

  def get_mem_str(self, addr):
    label = self.get_label(addr)
    if label != None:
      return "@%06x +%06x %s" % (label.addr, addr - label.addr, label.name)
    else:
      return "N/A"

  def trace_int_block(self, mode, addr, size, text="", level=logging.DEBUG, addon=""):
    log_mem_int.log(level, "%s(B): %06x: +%06x   %6s  [%s] %s", mode, addr, size, text, self.get_mem_str(addr), addon)

  def trace_int_mem(self, mode, width, addr, value, text="", level=logging.DEBUG, addon=""):
    val = self.trace_val_str[width] % value
    log_mem_int.log(level, "%s(%d): %06x: %s  %6s  [%s] %s", mode, 2**width, addr, val, text, self.get_mem_str(addr), addon)
