from LabelRange import LabelRange

from amitools.vamos.Log import log_mem
import logging

class LabelStruct(LabelRange):
  def __init__(self, name, addr, struct, size=0, offset=0):
    str_size = struct.get_size()
    if size < (str_size + offset):
      size = str_size + offset
    LabelRange.__init__(self, name, addr, size)
    self.struct = struct
    self.offset = offset
    self.struct_begin = addr + offset
    self.struct_end   = self.struct_begin + str_size
    self.struct_size  = str_size

  def trace_mem(self, mode, width, addr, val):
    delta = addr - self.struct_begin
    if delta >= 0 and delta < self.struct_size:
      try:
        name,off,val_type_name = self.struct.get_name_for_offset(delta, width)
        type_name = self.struct.get_type_name()
        addon = "%s+%d = %s(%s)+%d" % (type_name, delta, name, val_type_name, off)
        self.trace_mem_int(mode, width, addr, val, text="Struct", addon=addon, level=logging.INFO)
        return True
      except BaseException:
        return False
    else:
      LabelRange.trace_mem(self, mode, width, addr, val)
      return True
