from Exceptions import *
from AccessMemory import AccessMemory

# MainMemory manages the whole address map of the CPU
# Its divided up into pages of 64K
# So every address can be written as:
#
# xxyyyy -> page xx offset yyyy

class MainMemory:
  def __init__(self, raw_mem, error_tracker):
    self.raw_mem = raw_mem
    self.error_tracker = error_tracker
    self.access = AccessMemory(self)

  # reserve special range -> begin_addr
  def reserve_special_range(self, num_pages=1):
    return self.raw_mem.reserve_special_range(num_pages)

  def set_special_range_read_funcs(self, addr, num_pages=1, r8=None, r16=None, r32=None):
    self.raw_mem.set_special_range_read_funcs(addr, num_pages, r8, r16, r32)

  def set_special_range_write_funcs(self, addr, num_pages=1, w8=None, w16=None, w32=None):
    self.raw_mem.set_special_range_write_funcs(addr, num_pages, r8, r16, r32)

