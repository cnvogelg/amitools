import logging
from amitools.vamos.Log import *

MEMORY_WIDTH_BYTE = 0
MEMORY_WIDTH_WORD = 1
MEMORY_WIDTH_LONG = 2

class LabelManager:
  trace_val_str = ( "%02x      ", "%04x    ", "%08x" )

  def __init__(self):
    self.first  = None
    self.last   = None
    self.error_tracker = None # will be set later

  # This is now all done manually with doubly linked
  # lists. The reason for this is that the python built-in
  # lists are ill-performing as the list grows larger,
  # and this is a heavy-duty class.
  def add_label(self, range):
    assert range.next == None
    assert range.prev == None
    if self.last == None:
      assert self.first == None
      self.last  = range
      self.first = range
    else:
      self.last.next = range
      range.prev = self.last
      self.last = range

  def remove_label(self, range):
    if range.prev != None:
      range.prev.next = range.next
    if range.next != None:
      range.next.prev = range.prev
    if self.last == range:
      self.last = range.prev
    if self.first == range:
      self.first = range.next
    range.next = None
    range.prev = None

  def delete_labels_within(self,addr,size):
    # try to find compatible: release all labels within the given range
    # this is necessary because the label could be part of a puddle
    # that is released in one go.
    r     = self.first
    while r != None:
      if r.addr >= addr and r.addr + r.size <= addr + size:
        s = r.next
        log_mem_int.log(logging.WARN, "remove_labels_within: got= [@%06x +%06x]  have=%s", addr, size, r)
        self.remove_label(r)
        r = s
      else:
        r = r.next

  def get_all_labels(self):
    ranges = []
    r      = self.first
    while r != None:
      ranges.append(r)
      r = r.next
    return ranges

  def dump(self):
    r = self.first
    while r != None:
      print r
      r = r.next

  # This is called quite often and hence
  # a bit speed critical. It finds the
  # range within which the given address
  # lies.
  def get_label(self, addr):
    r = self.first
    while r != None:
      if r.addr <= addr and addr < r.end:
        return r
      r = r.next
    return None

  def get_intersecting_labels(self, addr, size):
    result = []
    r = self.first
    while r != None:
      if r.does_intersect(addr,size):
        result.append(r)
      r = r.next
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

  def get_disasm_info(self, addr):
    label = self.get_label(addr)
    if label != None:
      mem = "@%06x +%06x %s" % (label.addr, addr - label.addr, label.name)
      sym = label.get_symbol(addr)
      src = label.get_src_info(addr)
    else:
      mem = "N/A"
      sym = None
      src = None
    return (mem, sym, src)

  def trace_int_block(self, mode, addr, size, text="", level=logging.DEBUG, addon=""):
    log_mem_int.log(level, "%s(B): %06x: +%06x   %6s  [%s] %s", mode, addr, size, text, self.get_mem_str(addr), addon)

  def trace_int_mem(self, mode, width, addr, value, text="", level=logging.DEBUG, addon=""):
    val = self.trace_val_str[width] % value
    log_mem_int.log(level, "%s(%d): %06x: %s  %6s  [%s] %s", mode, 2**width, addr, val, text, self.get_mem_str(addr), addon)
