from amitools.vamos.MemoryBlock import MemoryBlock

from Log import log_mem
import logging

class MemoryStruct(MemoryBlock):
  def __init__(self, name, addr, struct, size=0, offset=0):
    str_size = struct.get_size()
    if size < (str_size + offset):
      size = str_size + offset
    MemoryBlock.__init__(self, name, addr, size)
    self.struct = struct
    self.offset = offset
    self.struct_begin = addr + offset
    self.struct_end   = self.struct_begin + str_size
    self.struct_size  = str_size
  
  def read_mem(self, width, addr):
    delta = addr - self.struct_begin
    if delta >= 0 and delta < self.struct_size:
      name,off,val_type_name = self.struct.get_name_for_offset(delta, width)
      val = MemoryBlock.read_mem_int(self, width, addr)
      type_name = self.struct.get_type_name()
      self.trace_read(width, addr, val, text="Struct  %s+%d = %s(%s)+%d" % (type_name, delta, name, val_type_name, off), level=logging.INFO)
      return val
    else:
      return MemoryBlock.read_mem(self, width, addr)

  def write_mem(self, width, addr, val):
    delta = addr - self.struct_begin
    if delta >= 0 and delta < self.struct_size:
      name,off,val_type_name = self.struct.get_name_for_offset(delta, width)
      type_name = self.struct.get_type_name()
      self.trace_write(width, addr, val, text="Struct  %s+%d = %s(%s)+%d" % (type_name, delta, name, val_type_name, off), level=logging.INFO)
      MemoryBlock.write_mem_int(self, width, addr, val)
    else:
      return MemoryBlock.write_mem(self, width, addr, val)
    
  def w_s(self, name, val):
    off,width,conv = self.struct.get_offset_for_name(name)
    if conv != None:
      val = conv[0](val)
    self.write_mem(width, self.struct_begin + off, val)
  
  def r_s(self, name, val):
    off,width,conv = self.struct.get_offset_for_name(name)
    val = self.read_mem(width, self.struct_begin + off)
    if conv != None:
      val = conv[1](val)
    return val