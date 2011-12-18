import ctypes
import struct

from Exceptions import *
from AccessMemory import AccessMemory

# MainMemory manages the whole address map of the CPU
# Its divided up into pages of 64K
# So every address can be written as:
#
# xxyyyy -> page xx offset yyyy

class MainMemory:
  
  op_reset = 0x04e70
  
  def __init__(self, raw_mem, error_tracker):
    self.raw_mem = raw_mem
    self.error_tracker = error_tracker
    self.access = AccessMemory(self)
  
  # reserve special range -> begin_addr
  def reserve_special_range(self, num_pages=1):
    return self.raw_mem.reserve_special_range(num_pages)
    
  def set_special_range_read_funcs(self, addr, num_pages=1, r8=None, r16=None, r32=None):
    for i in xrange(num_pages):
      if r8 != None:
        self.raw_mem.set_special_range_read_func(addr, 0, r8)
      if r16 != None:
        self.raw_mem.set_special_range_read_func(addr, 1, r16)
      if r32 != None:
        self.raw_mem.set_special_range_read_func(addr, 2, r32)
      addr += 0x10000

  def set_special_range_write_funcs(self, addr, num_pages=1, w8=None, w16=None, w32=None):
    for i in xrange(num_pages):
      if w8 != None:
        self.raw_mem.set_special_range_write_func(addr, 0, w8)
      if w16 != None:
        self.raw_mem.set_special_range_write_func(addr, 1, w16)
      if w32 != None:
        self.raw_mem.set_special_range_write_func(addr, 2, w32)
      addr += 0x10000

  def read_mem(self, width, addr):
    return self.raw_mem.read_ram(width, addr)
    
  def write_mem(self, width, addr, val):
    self.raw_mem.write_ram(width, addr, val)

  def read_block(self, addr, size, data):
    self.raw_mem.read_ram_block(addr,size,data)
  
  def write_block(self, addr, size, data):
    self.raw_mem.write_ram_block(addr,size,data)

  def clear_block(self, addr, size, value):
    self.raw_mem.clear_ram_block(addr,size,value)
