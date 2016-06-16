
class RomImg(object):
  def __init__(self, data_bytes, base_addr=0):
    self.addr = base_addr
    self.data = data_bytes
    self.size = len(data_bytes)
    self.is_writeable = type(data_bytes) is bytearray
    self.name = None
    self.short_name = None
    self.chk_sum_off = None
    self.is_kick = False

  def __repr__(self):
    return "RomImg(addr=%08x,size=%08x," \
           "is_writeable=%s,name=%s,short_name=%s," \
           "chk_sum_off=%s,is_kick=%s)" % \
      (self.addr, self.size,
       self.is_writeable,
       self.name, self.short_name,
       self.chk_sum_off, self.is_kick)

  def get_data(self):
    return self.data

  def make_writeable(self):
    if not self.writeable:
      self.data = bytearray(self.data)
      self.writeable = True

  def get_size(self):
    return self.size

  def get_size_kib(self):
    return self.size / 1024
