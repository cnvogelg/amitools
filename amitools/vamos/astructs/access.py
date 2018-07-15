
class AccessStruct(object):

  _size_to_width = [
      None, 0, 1, None, 2
  ]

  def __init__(self, mem, struct_def, struct_addr):
    self.mem = mem
    self.struct = struct_def(mem, struct_addr)
    self.trace_mgr = getattr(self.mem, 'trace_mgr', None)

  def w_s(self, name, val):
    struct, field = self.struct.write_field(name, val)
    if self.trace_mgr is not None:
      off = field.offset
      addr = struct.get_addr() + off
      tname = struct.get_type_name()
      addon = "%s+%d = %s" % (tname, off, name)
      width = self._size_to_width[field.size]
      self.trace_mgr.trace_int_mem('W', width, addr, val,
                                   text="Struct", addon=addon)

  def r_s(self, name):
    struct, field, val = self.struct.read_field_ext(name)
    if self.trace_mgr is not None:
      off = field.offset
      addr = struct.get_addr() + off
      tname = struct.get_type_name()
      addon = "%s+%d = %s" % (tname, off, name)
      width = self._size_to_width[field.size]
      self.trace_mgr.trace_int_mem('R', width, addr, val,
                                   text="Struct", addon=addon)
    return val

  def s_get_addr(self, name):
    return self.struct.get_addr_for_name(name)

  def r_all(self):
    """return a namedtuple with all values of the struct"""
    return self.struct.read_data()

  def w_all(self, nt):
    """set values stored in a named tuple"""
    self.struct.write_data(nt)

  def get_size(self):
    return self.struct.get_size()
