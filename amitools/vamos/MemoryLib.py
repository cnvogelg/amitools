from MemoryRange import MemoryRange
from MemoryStruct import MemoryStruct
from structure.ExecStruct import LibraryDef

import logging

class MemoryLib(MemoryStruct):
  
  op_rts = 0x4e75
  op_jmp = 0x4ef9
  
  def __init__(self, name, addr, num_vectors, pos_size, struct=LibraryDef, lib=None, context=None):
    self.lib = lib
    self.ctx = context

    self.num_vectors = num_vectors
    self.pos_size = pos_size
    self.neg_size = num_vectors * 6
    
    self.lib_begin = addr
    self.lib_base  = addr + self.neg_size
    self.lib_end   = self.lib_base + self.pos_size

    MemoryStruct.__init__(self, name, addr, struct, size=self.pos_size + self.neg_size, offset=self.neg_size)
    
  def __str__(self):
    return "%s base=%06x %s" %(MemoryRange.__str__(self),self.lib_base,str(self.lib))

  def set_all_vectors(self, vectors):
    """set all library vectors to valid addresses"""
    if len(vectors) != self.num_vectors:
      raise ValueError("Invalid number of library vectors given!")
    addr = self.lib_base - 6
    for v in vectors:
      self.write_mem(1,addr,self.op_jmp)
      self.write_mem(2,addr+2,v)
      addr -= 6

  def get_lib_base(self):
    return self.lib_base
    
  def get_neg_size(self):
    return self.neg_size
    
  def get_pos_size(self):
    return self.pos_size

  def get_lib(self):
    return self.lib

  def read_mem(self, width, addr):
    # a possible trap?
    if addr < self.lib_base and width == 1:
      val = self.read_mem_int(1,addr)
      # is it trapped?
      if val != self.op_jmp:
        val = self.op_rts
        delta = self.lib_base - addr
        off = delta / 6
        addon = "-%d [%d]" % (delta,off)
        self.trace_read(width, addr, val, text="TRAP", level=logging.INFO, addon=addon)
        self.lib.call_vector(off,self,self.ctx)
        return val
      # native lib jump
      else:
        delta = self.lib_base - addr
        addon = "-%d" % delta
        self.trace_read(width, addr, val, text="JUMP", level=logging.INFO, addon=addon)
        return val
    # no use regular access
    return MemoryStruct.read_mem(self, width, addr)
