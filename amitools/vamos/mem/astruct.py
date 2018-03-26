import collections


struct_pool = {}


class InvalidAmigaTypeException(Exception):
  def __init__(self, type_name):
    self.type_name = type_name

  def __str__(self):
    return self.type_name


def w_bptr(addr):
  return addr >> 2


def r_bptr(addr):
  return addr << 2


class AmigaStruct:

  # overwrite these in derived class!
  _name = None
  _format = None

  # name all internal types
  # and map to (byte width in 2**n, (w_convert, r_convert), signed)
  _types = {
      'UBYTE': (0, None, False),
      'BYTE': (0, None, True),
      'char': (0, None, False),
      'UWORD': (1, None, False),
      'WORD': (1, None, True),
      'ULONG': (2, None, False),
      'LONG': (2, None, True),
      'APTR': (2, None, False),
      'BPTR': (2, (w_bptr, r_bptr), False),
      'BSTR': (2, (w_bptr, r_bptr), False),
      'VOIDFUNC': (2, None, False),
      'void': (2, None, False),
  }
  _ptr_type = (2, None, False)

  _size_to_width = [
      None, 0, 1, None, 2
  ]

  def __init__(self):
    struct_pool[self._name] = self

    # calc size of struct
    size = 0
    offsets = []
    sizes = []
    sub_types = []
    base_types = []
    pointers = []
    off = 0
    lookup = {}
    num = 0
    for e in self._format:
      # store offset
      offsets.append(off)

      # fetch type name
      type_name = e[0]
      if not self.validate_type_name(type_name):
        raise InvalidAmigaTypeException(type_name)

      # calc size
      e_size = self.lookup_type_width(type_name)
      sizes.append(e_size)
      off += e_size

      # is pointer?
      pointers.append(self._is_pointer(type_name))
      sub_types.append(self.get_sub_type(type_name))
      base_types.append(self.get_base_type(type_name))

      # store name -> index mapping
      lookup[e[1]] = num
      num += 1

    self._offsets = offsets
    self._sizes = sizes
    self._total_size = off
    self._lookup = lookup
    self._sub_types = sub_types
    self._base_types = base_types
    self._pointers = pointers
    self._nt_class = None

  def __str__(self):
    return "[Struct: %s size=%d]" % (self._name, self._total_size)

  def get_size(self):
    return self._total_size

  def get_type_name(self):
    return self._name

  def get_all_field_names(self):
    return map(lambda x: x[1], self._format)

  def get_data_class(self):
    if self._nt_class is None:
      name = self._name + "Data"
      fields = self.get_all_field_names()
      self._nt_class = collections.namedtuple(name, fields)
    return self._nt_class

  def read_data(self, mem, addr):
    cls = self.get_data_class()
    vals = []
    num = len(self._format)
    for idx in xrange(num):
      val = self.read_field_index(mem, addr, idx)
      vals.append(val)
    return cls(*vals)

  def write_data(self, mem, addr, data):
    num = len(self._format)
    for idx in xrange(num):
      val = data[idx]
      self.write_field_index(mem, addr, idx, val)

  def read_field_index(self, mem, addr, index, do_conv=True):
    off = self._offsets[index]
    addr += off
    size = self._sizes[index]
    sub_type = self._sub_types[index]
    if sub_type is not None:
      return sub_type.read_data(mem, addr)
    else:
      base_type = self._base_types[index]
      if base_type is not None:
        return self._read_base(mem, base_type, addr, do_conv)
      else:
        width = self._size_to_width[size]
        return mem.read(width, addr)

  def _read_base(self, mem, base_type, addr, do_conv=True):
    width = base_type[0]
    conv = base_type[1]
    signed = base_type[2]
    # read value
    if signed:
      val = mem.reads(width, addr)
    else:
      val = mem.read(width, addr)
    # convert?
    if conv != None and do_conv:
      val = conv[1](val)
    return val

  def write_field_index(self, mem, addr, index, val, do_conv=True):
    off = self._offsets[index]
    addr += off
    size = self._sizes[index]
    sub_type = self._sub_types[index]
    if sub_type is not None:
      sub_type.write_data(mem, addr, val)
    else:
      base_type = self._base_types[index]
      if base_type is not None:
        self._write_base(mem, base_type, addr, val)
      else:
        width = self._size_to_width[size]
        mem.write(width, addr, val)

  def _write_base(self, mem, base_type, addr, val, do_conv=True):
    width = base_type[0]
    conv = base_type[1]
    signed = base_type[2]
    # convert?
    if conv != None and do_conv:
      val = conv[0](val)
    # write value
    if signed:
      mem.writes(width, addr, val)
    else:
      mem.write(width, addr, val)

  def read_field(self, mem, addr, name, do_conv=True):
    off, base_type = self.get_offset_for_name(name)
    addr += off
    val = self._read_base(mem, base_type, addr, do_conv)
    width = base_type[0]
    return val, off, width

  def write_field(self, mem, addr, name, val, do_conv=True):
    off, base_type = self.get_offset_for_name(name)
    addr += off
    self._write_base(mem, base_type, addr, val, do_conv)
    width = base_type[0]
    return off, width

  def dump(self, indent=0, num=0, base=0, name=""):
    istr = "  " * indent
    print "     @%04d       %s %s {" % (base, istr, self._name)
    i = 0
    for f in self._format:
      off = self._offsets[i] + base
      size = self._sizes[i]
      sub_type = self._sub_types[i]
      if sub_type != None:
        num = sub_type.dump(indent=indent+1, num=num, base=off, name=f[1])
      else:
        print "%04d @%04d/%04x +%04d %s   %-10s %-20s  (ptr=%s, sub=%s)" % \
            (num, off, off, size, istr, f[0], f[1],
             self._pointers[i], sub_type != None)
        num += 1
      i += 1
    total = self._total_size
    off = total + base
    print "     @%04d =%04d %s } %s" % (off, total, istr, name)
    return num

  # return (name, delta, type_name)
  def get_name_for_offset(self, offset, width, prefix=""):
    num = self.get_index_for_offset(offset)
    if num == None:
      raise ValueError("Invalid offset %s: %d" % (self, offset))
    type_offset = self._offsets[num]
    delta = offset - type_offset
    sub_type = self._sub_types[num]
    pointer = self._pointers[num]
    format = self._format[num]
    name = prefix + format[1]
    # a pointer type
    if pointer:
      return (name, delta, format[0])
    # a embedded sub type
    elif sub_type != None:
      return sub_type.get_name_for_offset(delta, width, prefix=name+".")
    # a base type
    else:
      base_type = format[0]
      type_width = self._types[base_type][0]
      return (name, delta, base_type)

  # return (off, width, convert_func_pair)
  def get_offset_for_name(self, name):
    parts = name.split('.')
    return self._get_offset_loop(parts)

  def _get_offset_loop(self, parts, base=0):
    name = parts[0]
    if not self._lookup.has_key(name):
      raise ValueError("Invalid Type key %s: %s %s" %
                       (self, name, self._lookup))
    num = self._lookup[name]

    type_offset = base + self._offsets[num]
    pointer = self._pointers[num]
    sub_type = self._sub_types[num]
    format = self._format[num]

    # last one
    if len(parts) == 1:
      # a pointer type -> return pointer itself
      if pointer:
        return (type_offset, self._ptr_type)
      # a embedded sub type -> get first elemen of sub type
      elif sub_type != None:
        first_name = sub_type._format[0][1]
        return sub_type._get_offset_loop([first_name], base=type_offset)
      # a base type
      else:
        base_type = self._gen_pure_name(format[0])
        base_format = self._types[base_type]
        return (type_offset, base_format)
    # more names:
    else:
      if sub_type != None:
        return sub_type._get_offset_loop(parts[1:], base=type_offset)
      else:
        raise ValueError("Type key is no sub type: %s: %s" %
                         (self._name, name))

  def get_index_for_offset(self, offset):
    if offset < 0:
      return None
    num = -1
    begin = 0
    for o in self._offsets:
      if offset < o:
        return num
      num += 1
    total = self._total_size
    if offset >= total:
      return None
    return num

  def get_sub_type(self, full_type_name):
    if self._is_pointer(full_type_name):
      return None
    type_name = self._gen_pure_name(full_type_name)
    if struct_pool.has_key(type_name):
      return struct_pool[type_name]
    else:
      return None

  def get_base_type(self, full_type_name):
    if self._is_pointer(full_type_name):
      return None
    type_name = self._gen_pure_name(full_type_name)
    if self._types.has_key(type_name):
      return self._types[type_name]
    else:
      return None

  def validate_type_name(self, full_type_name):
    type_name = self._gen_pure_name(full_type_name)
    # is it an internal type
    if self._types.has_key(type_name):
      return True
    elif struct_pool.has_key(type_name):
      return True
    else:
      return False

  def lookup_type_width(self, full_type_name):
    # array?
    comp = full_type_name.split('|')
    type_name = comp[0]
    array_mult = 1
    for m in comp[1:]:
      array_mult *= int(m)

    # its a pointer ;)
    if self._is_pointer(type_name):
      base = 4
    # look for standard type
    elif self._types.has_key(type_name):
      base = 2 ** self._types[type_name][0]
    # look for user type
    elif struct_pool.has_key(type_name):
      t = struct_pool[type_name]
      base = t.get_size()
    else:
      raise InvalidAmigaTypeException(type_name)

    return array_mult * base

  def _gen_pure_name(self, name):
    # remove array post fixes and pointers
    comp = name.split('|')
    type_name = comp[0].split('*')[0]
    return type_name

  def _is_pointer(self, name):
    return name.find('*') != -1
