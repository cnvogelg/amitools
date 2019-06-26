import collections
from .baddr import BAddr


class AmigaStruct(object):

  # store all children of this class
  _struct_pool = {}

  # overwrite in derived class!
  _format = None

  # name all internal types
  # and map to (byte width in 2**n, is_bcpl_ptr, signed)
  _types = {
      'UBYTE': (0, False, False),
      'BYTE': (0, False, True),
      'char': (0, False, False),
      'UWORD': (1, False, False),
      'WORD': (1, False, True),
      'ULONG': (2, False, False),
      'LONG': (2, False, True),
      'APTR': (2, False, False),
      'BPTR': (2, True, False),
      'BSTR': (2, True, False),
      'VOIDFUNC': (2, False, False),
      'void': (2, False, False),
  }
  _ptr_type = (2, False, False)

  # these values are filled by the decorator
  _type_name = None
  _total_size = None
  _fields = None
  _name_to_field = None
  _field_names = None
  _num_fields = None
  _data_class = None

  @classmethod
  def get_type_name(cls):
    return cls._type_name

  @classmethod
  def get_size(cls):
    return cls._total_size

  @classmethod
  def get_fields(cls):
    return cls._fields

  @classmethod
  def get_field_by_name(cls, name):
    return cls._name_to_field[name]

  @classmethod
  def get_field_by_offset(cls, offset):
    for f in cls._fields:
      end = f.offset + f.size
      if offset >= f.offset and offset < end:
        return f

  @classmethod
  def get_fields_by_offset(cls, offset):
    res = []
    while True:
      f = cls.get_field_by_offset(offset)
      if f is None:
        break
      res.append(f)
      s = f.struct_type
      if not s or f.is_pointer:
        break
      offset -= f.offset
      cls = s
    return res

  @classmethod
  def get_fields_by_path(cls, name):
    parts = name.split('.')
    return cls.get_fields_for_parts(parts)

  @classmethod
  def get_fields_for_parts(cls, parts):
    struct = cls
    res = []
    for name in parts:
      field = struct.get_field_by_name(name)
      res.append(field)
      struct = field.struct_type
    return res

  @classmethod
  def get_field_offset_by_name(cls, name):
    field = cls.get_field_by_name(name)
    return field.offset

  @classmethod
  def get_field_offset_for_path(cls, name):
    fields = cls.get_fields_by_path(name)
    offsets = [x.offset for x in fields]
    return sum(offsets)

  @classmethod
  def get_field_by_index(cls, idx):
    return cls._fields[idx]

  @classmethod
  def get_field_names(cls):
    return cls._field_names

  @classmethod
  def get_num_fields(cls):
    return cls._num_fields

  @classmethod
  def get_data_class(cls):
    return cls._data_class

  @classmethod
  def find_struct(cls, name):
    if name in cls._struct_pool:
      return cls._struct_pool[name]

  @classmethod
  def get_all_structs(cls):
    return list(cls._struct_pool.values())

  @classmethod
  def get_all_struct_names(cls):
    return list(cls._struct_pool.keys())

  @classmethod
  def dump_type(self, indent=0, num=0, base=0, name="", data=None):
    istr = "  " * indent
    print("     @%04d       %s %s {" % (base, istr, self._type_name))
    i = 0
    for f in self._fields:
      offset = f.offset
      size = f.size
      struct_type = f.struct_type
      if struct_type and not f.is_pointer:
        if data:
          sub_data = data[i]
        else:
          sub_data = None
        num = struct_type.dump_type(
            indent=indent+1, num=num, base=offset, name=f.name, data=sub_data)
      else:
        if data:
          data_str = "= %-10s" % str(data[i])
        else:
          data_str = ""
        print("#%04d %04d @%04d/%04x +%04d %s  %s  %-10s %-20s  (ptr=%s, sub=%s)" % \
            (i, num, offset, offset, size, istr, data_str, f.type_sig, f.name,
             f.is_pointer, bool(struct_type)))
        num += 1
      i += 1
    total = self._total_size
    off = total + base
    print("     @%04d =%04d %s } %s" % (off, total, istr, name))
    return num

  # ----- instance -----

  def __init__(self, mem, addr):
    self._mem = mem
    self._addr = addr
    self._parent = None

  def __eq__(self, other):
    if type(other) is int:
      return self._addr == other
    elif isinstance(other, AmigaStruct):
      return self._addr == other._addr
    else:
      return NotImplemented

  def __str__(self):
    return "[AStruct:%s,@%06x+%06x]" % \
        (self._type_name, self._addr, self._total_size)

  def get_mem(self):
    return self._mem

  def get_addr(self):
    return self._addr

  def get_parent(self):
    return self._parent

  def get_path_name(self):
    my_name = self.get_type_name()
    if self._parent:
      return self._parent.get_path_name() + "." + my_name
    else:
      return my_name

  def get_field_path_name(self, field):
    my_name = field.name
    if self._parent:
      addr = self._addr + field.offset
      st, p_field, _ = self._parent.get_struct_field_for_addr(
          addr, recurse=False)
      return self._parent.get_field_path_name(p_field) + "." + my_name
    else:
      return my_name

  def read_data(self):
    cls = self._data_class
    vals = []
    for idx in range(self._num_fields):
      val = self.read_field_index(idx)
      vals.append(val)
    return cls(*vals)

  def write_data(self, data):
    for idx in range(self._num_fields):
      val = data[idx]
      self.write_field_index(idx, val)

  def read_field_index(self, index):
    field = self._fields[index]
    addr = self._addr + field.offset
    # pointer
    if field.is_pointer:
      val = self._mem.r32(addr)
      if field.is_baddr:
        val = BAddr(val)
      return val
    # embedded struct type
    elif field.struct_type:
      struct = self.create_struct(field)
      return struct.read_data()
    else:
      base_type = field.base_type
      width = base_type[0]
      is_baddr = base_type[1]
      signed = base_type[2]
      # read value
      if signed:
        val = self._mem.reads(width, addr)
      else:
        val = self._mem.read(width, addr)
      # auto convert baddr
      if is_baddr:
        val = BAddr(val)
      return val

  def write_field_index(self, index, val):
    field = self._fields[index]
    addr = self._addr + field.offset
    # pointer
    if field.is_pointer:
      if field.is_baddr:
        if type(val) is not BAddr:
          val = BAddr.from_addr(int(val))
        val = val.get_baddr()
      self._mem.w32(addr, val)
    # embedded struct type
    elif field.struct_type:
      struct = self.create_struct(field)
      return struct.write_data(val)
    else:
      base_type = field.base_type
      width = base_type[0]
      is_baddr = base_type[1]
      signed = base_type[2]
      # convert?
      if is_baddr:
        if type(val) is not BAddr:
          val = BAddr.from_addr(int(val))
        val = val.get_baddr()
      # write value
      if signed:
        self._mem.writes(width, addr, val)
      else:
        self._mem.write(width, addr, val)

  def read_field(self, name):
    struct, field = self.get_struct_field_for_name(name)
    return struct.read_field_index(field.index)

  def read_field_ext(self, name):
    struct, field = self.get_struct_field_for_name(name)
    val = struct.read_field_index(field.index)
    return struct, field, val

  def write_field(self, name, val):
    struct, field = self.get_struct_field_for_name(name)
    struct.write_field_index(field.index, val)
    return struct, field

  def dump(self):
    data = self.read_data()
    self.dump_type(data=data)

  def get_field_addr(self, field):
    return self._addr + field.offset

  def get_struct_field_for_addr(self, addr, recurse=True):
    return self.get_struct_field_for_offset(addr - self._addr, recurse)

  def get_struct_field_for_offset(self, offset, recurse=True):
    """return (struct, field, delta) or None"""
    for field in self._fields:
      if offset < field.end:
        delta = offset - field.offset
        # sub struct
        if field.struct_type and not field.is_pointer and recurse:
          struct = self.create_struct(field)
          return struct.get_struct_field_for_offset(delta)
        # no sub struct
        return self, field, delta

  def get_addr_for_name(self, name):
    struct, field = self.get_struct_field_for_name(name)
    return struct._addr + field.offset

  def get_struct_field_for_name(self, name):
    """return (struct, field)"""
    parts = name.split('.')
    return self._get_struct_field_for_parts(parts)

  def _get_struct_field_for_parts(self, parts):
    name = parts[0]
    field = self.get_field_by_name(name)
    # last one in path
    if len(parts) == 1:
      return self, field
    # more names: expect embedded struct
    else:
      struct = self.create_struct(field)
      return struct._get_struct_field_for_parts(parts[1:])

  def create_struct(self, field):
    st = field.struct_type
    if st is None:
      return None
    struct = st(self._mem, self._addr + field.offset)
    struct._parent = self
    return struct

  def __getattr__(self, name):
    if name in self._name_to_field:
      field = self._name_to_field[name]
      if field.struct_type:
        # allow to access sub struct
        return self.create_struct(field)
      else:
        # access value
        return self.read_field_index(field.index)
    else:
      raise AttributeError

  def __setattr__(self, name, val):
    if name[0] == '_':
      object.__setattr__(self, name, val)
    elif name in self._name_to_field:
      field = self._name_to_field[name]
      self.write_field_index(field.index, val)
    else:
      raise AttributeError
