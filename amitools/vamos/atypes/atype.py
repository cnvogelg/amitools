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

  @classmethod
  def get_type_struct(cls):
    return cls._struct_def

  def __init__(self, mem, addr):
    assert type(addr) is int
    self.mem = mem
    self.addr = addr
    self.struct = self._struct_def(mem, addr)
    # allocation extra info
    self.alloc = None
    self.mem_obj = None
    self.size = None

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

  def get_size(self):
    if self.size:
      return self.size
    else:
      return self.get_type_size()

  def write_data(self):
    return self.struct.write_data()

  @classmethod
  def alloc(cls, alloc, tag=None, size=None, add_label=True):
    if tag is None:
      tag = cls._type_name
    if size is None:
      size = cls.get_type_size()
    struct = cls.get_type_struct()
    mem_obj = alloc.alloc_struct(tag, struct, size, add_label=add_label)
    mem = alloc.get_mem()
    obj = cls(mem, mem_obj.addr)
    obj.alloc = alloc
    obj.mem_obj = mem_obj
    obj.size = size
    return obj

  def free(self):
    if self.alloc:
      self.alloc.free_struct(self.mem_obj)
      self.alloc = None
      self.mem_obj = None
      self.addr = 0
    else:
      raise RuntimeError("can't free")
