import logging

class AccessStruct(object):
  def __init__(self, mem, struct_def, struct_addr):
    self.mem = mem
    self.struct_addr = struct_addr
    self.struct_def = struct_def
    self.struct_type_name = self.struct_def.get_type_name()
    self.trace_mgr = getattr(self.mem, 'trace_mgr', None)

  def w_s(self, name, val):
    off,width,conv = self.struct_def.get_offset_for_name(name)
    if conv != None:
      val = conv[0](val)
    addr = self.struct_addr + off
    self.mem.write(width, addr, val)
    if self.trace_mgr is not None:
      addon="%s+%d = %s" % (self.struct_type_name, off, name)
      self.trace_mgr.trace_int_mem('W', width, addr, val,
                                   text="Struct", addon=addon)

  def r_s(self, name):
    off,width,conv = self.struct_def.get_offset_for_name(name)
    addr = self.struct_addr + off
    val = self.mem.read(width, addr)
    if conv != None:
      val = conv[1](val)
    if self.trace_mgr is not None:
      addon="%s+%d = %s" % (self.struct_type_name, off, name)
      self.trace_mgr.trace_int_mem('R', width, addr, val,
                                   text="Struct", addon=addon)
    return val

  def s_get_addr(self, name):
    off,width,conv = self.struct_def.get_offset_for_name(name)
    return self.struct_addr + off
