
class AccessStruct(object):
  def __init__(self, mem, struct_def, struct_addr):
    self.mem = mem
    self.struct_addr = struct_addr
    self.struct_def = struct_def
    self.struct_type_name = self.struct_def.get_type_name()
    self.trace_mgr = getattr(self.mem, 'trace_mgr', None)

  def w_s(self, name, val, do_conv=True):
    off, width = self.struct_def.write_field(
        self.mem, self.struct_addr, name, val, do_conv)
    if self.trace_mgr is not None:
      addr = self.struct_addr + off
      addon = "%s+%d = %s" % (self.struct_type_name, off, name)
      self.trace_mgr.trace_int_mem('W', width, addr, val,
                                   text="Struct", addon=addon)

  def r_s(self, name, do_conv=True):
    val, off, width = self.struct_def.read_field(
        self.mem, self.struct_addr, name, do_conv)
    if self.trace_mgr is not None:
      addr = self.struct_addr + off
      addon = "%s+%d = %s" % (self.struct_type_name, off, name)
      self.trace_mgr.trace_int_mem('R', width, addr, val,
                                   text="Struct", addon=addon)
    return val

  def s_get_addr(self, name):
    off, width, conv = self.struct_def.get_offset_for_name(name)
    return self.struct_addr + off

  def r_all(self):
    """return a namedtuple with all values of the struct"""
    return self.struct_def.read_data(self.mem, self.struct_addr)

  def w_all(self, nt):
    """set values stored in a named tuple"""
    self.struct_def.write_data(self.mem, self.struct_addr, nt)
