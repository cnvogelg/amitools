class AmigaType(object):

  # will be set by decorator
  _type_pool = {}
  _struct_def = None
  _type_name = None

  @classmethod
  def find_type(cls, name):
    if name in cls._type_pool:
      return cls._type_pool[name]

  @classmethod
  def get_type_name(cls):
    return cls._type_name

  @classmethod
  def get_type_size(cls):
    return cls._struct_def.get_size()

  def __init__(self, mem, addr):
    assert type(addr) is int
    self.mem = mem
    self.addr = addr
    self.struct = self._struct_def(mem, addr)

  def __eq__(self, other):
    if type(other) is int:
      return self.addr == other
    elif isinstance(other, AmigaType):
      return self.addr == other.addr
    else:
      return NotImplemented

  def get_mem(self):
    return self.mem

  def get_addr(self):
    return self.addr

  def read_data(self):
    return self.struct.read_data()

  def write_data(self):
    return self.struct.write_data()
