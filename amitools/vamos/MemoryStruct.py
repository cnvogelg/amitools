from amitools.vamos.MemoryBlock import MemoryBlock

from Log import log_mem
import logging

class MemoryStruct(MemoryBlock):
  def __init__(self, name, addr, struct):
    MemoryBlock.__init__(self, name, addr, struct.get_size())
    self.struct = struct
  
  def read_mem(self, width, addr):
    delta = addr - self.addr
    name,off,val_type_name = self.struct.get_name_for_offset(delta, width)
    val = MemoryBlock.read_mem_int(self, width, addr)
    type_name = self.struct.get_type_name()
    self.trace_read(width, addr, val, text="Struct  %s+%d = %s(%s)+%d" % (type_name, delta, name, val_type_name, off), level=logging.INFO)
    return val

  def write_mem(self, width, addr, val):
    delta = addr - self.addr
    name,off,val_type_name = self.struct.get_name_for_offset(delta, width)
    type_name = self.struct.get_type_name()
    self.trace_write(width, addr, val, text="Struct  %s+%d = %s(%s)+%d" % (type_name, delta, name, val_type_name, off), level=logging.INFO)
    return MemoryBlock.write_mem_int(self, width, addr)
    
  def w_s(self, name, val):
    off,width,conv = self.struct.get_offset_for_name(name)
    if conv != None:
      val = conv[0](val)
    self.wfunc[width](self.addr + off, val)
  
  def r_s(self, name, val):
    off,width,conv = self.struct.get_offset_for_name(name)
    val = self.rfunc[width](self.addr + off)
    if conv != None:
      val = conv[1](val)
    return val