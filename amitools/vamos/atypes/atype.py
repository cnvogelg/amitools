from .cstring import CString


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
    self._mem = mem
    self._addr = addr
    self._struct = self._struct_def(mem, addr)
    # allocation extra info
    self._alloc = None
    self._mem_obj = None
    self._size = None

  def __eq__(self, other):
    if type(other) is int:
      return self._addr == other
    elif isinstance(other, AmigaType):
      return self._addr == other._addr
    else:
      return NotImplemented

  def get_mem(self):
    return self._mem

  def get_addr(self):
    return self._addr

  def read_data(self):
    return self._struct.read_data()

  def get_size(self):
    if self._size:
      return self._size
    else:
      return self.get_type_size()

  def write_data(self):
    return self._struct.write_data()

  @classmethod
  def init_from(cls, other):
    if isinstance(other, AmigaType):
      return cls(other._mem, other._addr)
    else:
      raise ValueError("no AType!")

  @classmethod
  def alloc(cls, alloc, tag=None, size=None, add_label=True):
    return cls._alloc(alloc, tag=tag, size=size, add_label=add_label)

  @classmethod
  def _alloc(cls, alloc, tag=None, size=None, add_label=True):
    if tag is None:
      tag = cls._type_name
    if size is None:
      size = cls.get_type_size()
    struct = cls.get_type_struct()
    mem_obj = alloc.alloc_struct(tag, struct, size, add_label=add_label)
    mem = alloc.get_mem()
    obj = cls(mem, mem_obj.addr)
    obj._alloc = alloc
    obj._mem_obj = mem_obj
    obj._size = size
    return obj

  def free(self):
    if self._alloc:
      self._alloc.free_struct(self._mem_obj)
      self._alloc = None
      self._mem_obj = None
      self._addr = 0
    else:
      raise RuntimeError("can't free")

  def __getattr__(self, name):
    # find associated getter
    if name.startswith('get_') or name.startswith('set_'):
      raise AttributeError
    func_name = 'get_' + name
    func = getattr(self, func_name, None)
    if func:
      return func()
    else:
      raise AttributeError

  def __setattr__(self, name, val):
    if name[0] == '_':
      object.__setattr__(self, name, val)
    else:
      func_name = 'set_' + name
      func = getattr(self, func_name, None)
      if func:
        func(val)
      else:
        raise AttributeError


class AmigaTypeWithName(AmigaType):
  def __init__(self, mem, addr, alloc=None):
    AmigaType.__init__(self, mem, addr)
    # extra alloc info
    self._name_cstr = None

  def set_name(self, name):
    pass

  @classmethod
  def alloc(cls, alloc, name=None):
    obj = cls._alloc(alloc, name)
    if name:
      obj._name_cstr = CString.alloc(alloc, name)
      obj.set_name(obj._name_cstr)
    return obj

  def free(self):
    AmigaType.free(self)
    if self._name_cstr:
      self._name_cstr.free()
