import logging
from AccessMemory import AccessMemory

class AccessStruct(AccessMemory):
  def __init__(self, mem, struct_def, struct_addr=0):
    AccessMemory.__init__(self,mem)
    if struct_addr == 0:
      struct_addr = mem.addr
    self.struct_addr = struct_addr
    self.struct_def = struct_def
    self.struct_type_name = self.struct_def.get_type_name()
  
  def w_s(self, name, val):
    off,width,conv = self.struct_def.get_offset_for_name(name)
    if conv != None:
      val = conv[0](val)
    addr = self.struct_addr + off
    self.mem.write_mem(width, addr, val)
    if self.label_mgr != None:
      self.label_mgr.trace_int_mem('W', width, addr, val, text="Struct", addon="%s+%d = %s" % (self.struct_type_name, off, name), level=logging.INFO)

  def r_s(self, name):
    off,width,conv = self.struct_def.get_offset_for_name(name)
    addr = self.struct_addr + off
    val = self.mem.read_mem(width, addr)
    if conv != None:
      val = conv[1](val)
    if self.label_mgr != None:
      self.label_mgr.trace_int_mem('R', width, addr, val, text="Struct", addon="%s+%d = %s" % (self.struct_type_name, off, name), level=logging.INFO)
    return val

  def s_get_addr(self, name):
    off,width,conv = self.struct_def.get_offset_for_name(name)
    return self.struct_addr + off
