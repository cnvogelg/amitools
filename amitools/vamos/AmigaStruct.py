struct_pool = {}

class InvalidAmigaTypeException(Exception):
  def __init__(self, type_name):
    self.type_name = type_name
  def __str__(self):
    return self.type_name

class AmigaStruct:
  
  # name all internal types and map to byte width in 2**n
  _types = {
    'UBYTE' : 0,
    'BYTE' : 0,
    'char' : 0,
    'UWORD' : 1,
    'WORD' : 1,
    'ULONG' : 2,
    'LONG' : 2,
    'APTR' : 2,
    'VOIDFUNC' : 2
  }
  
  def __init__(self):
    struct_pool[self._name] = self
    
    # calc size of struct
    size = 0
    offsets = []
    sizes = []
    sub_types = []
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
      
      # store name -> index mapping
      lookup[e[1]] = num
      num += 1
    
    self._offsets = offsets
    self._sizes = sizes
    self._total_size = off
    self._lookup = lookup
    self._sub_types = sub_types
    self._pointers = pointers
  
  def get_size(self):
    return self._total_size
    
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
        print "%04d @%04d +%04d %s   %-10s %-20s  (ptr=%s, sub=%s)" % (num, off, size, istr, f[0], f[1], self._pointers[i], sub_type!=None)
        num += 1
      i += 1
    total = self._total_size
    off = total + base
    print "     @%04d =%04d %s } %s" % (off,total,istr,name)
    return num
  
  # return (name, valid_width)
  def get_name_for_offset(self, offset, width, prefix=""):
    num = self.get_index_for_offset(offset)
    if num == None:
      return (None,false)
    type_offset = self._offsets[num]
    delta = offset - type_offset
    sub_type = self._sub_types[num]
    pointer = self._pointers[num]
    format = self._format[num]
    name = format[1]
    # a pointer type
    if pointer:
      return (prefix+name,delta)
    # a embedded sub type
    elif sub_type != None:
      return sub_type.get_name_for_offset(delta, width, prefix=name+".")
    # a base type
    else:
      base_type = format[0]
      type_width = self._types[base_type]
      return (prefix+name,delta)
  
  def get_index_for_offset(self, offset):
    num = -1
    begin = 0
    for o in self._offsets:
      if offset < o:
        return num
      num += 1
    total = self._total_size
    if offset >= total:
      return None
    return total
      
  def get_sub_type(self, full_type_name):
    if self._is_pointer(full_type_name):
      return None
    type_name = self._gen_pure_name(full_type_name)
    if struct_pool.has_key(type_name):
      return struct_pool[type_name]
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
      base = 2 ** self._types[type_name] 
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

  def _is_pointer(self,name):
    return name.find('*') != -1
