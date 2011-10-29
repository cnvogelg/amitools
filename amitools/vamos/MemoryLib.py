from MemoryRange import MemoryRange
from MemoryStruct import MemoryStruct
from AccessStruct import AccessStruct
from structure.ExecStruct import LibraryDef

import logging

class MemoryLib(MemoryStruct):
  
  op_jmp = 0x4ef9
  
  def __init__(self, name, addr, size, lib_base, struct):
    MemoryStruct.__init__(self, name, addr, struct, size=size, offset=lib_base - addr)
    self.lib_base = lib_base
    
  def __str__(self):
    return "%s base=%06x" %(MemoryStruct.__str__(self),self.lib_base)

  def read_mem(self, width, addr):
    # a possible trap?
    if addr < self.lib_base and width == 1:
      val = self.read_mem_int(1,addr)
      # is it trapped?
      if val != self.op_jmp:
        delta = self.lib_base - addr
        off = delta / 6
        addon = "-%d [%d]" % (delta,off)
        self.trace_read(width, addr, val, text="TRAP", level=logging.INFO, addon=addon)
      # native lib jump
      else:
        delta = self.lib_base - addr
        addon = "-%d" % delta
        self.trace_read(width, addr, val, text="JUMP", level=logging.INFO, addon=addon)
      return val
    # no use regular access
    return MemoryStruct.read_mem(self, width, addr)
