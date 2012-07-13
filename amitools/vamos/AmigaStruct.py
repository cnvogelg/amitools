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
  # and map to (byte width in 2**n, w_convert, r_convert)
  _types = {
    'UBYTE' : (0,None),
    'BYTE' : (0,None),
    'char' : (0,None),
    'UWORD' : (1,None),
    'WORD' : (1,None),
    'ULONG' : (2,None),
    'LONG' : (2,None),
    'APTR' : (2,None),
    'BPTR' : (2,(w_bptr,r_bptr)),
    'BSTR' : (2,(w_bptr,r_bptr)),
    'VOIDFUNC' : (2,None),
    'void' : (2,None),
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
  
  def __str__(self):
    return "[Struct: %s size=%d]" % (self._name,self._total_size)
  
  def get_size(self):
    return self._total_size
    
  def get_type_name(self):
    return self._name
    
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
        print "%04d @%04d/%04x +%04d %s   %-10s %-20s  (ptr=%s, sub=%s)" % (num, off, off, size, istr, f[0], f[1], self._pointers[i], sub_type!=None)
        num += 1
      i += 1
    total = self._total_size
    off = total + base
    print "     @%04d =%04d %s } %s" % (off,total,istr,name)
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
      return (name,delta,format[0])
    # a embedded sub type
    elif sub_type != None:
      return sub_type.get_name_for_offset(delta, width, prefix=name+".")
    # a base type
    else:
      base_type = format[0]
      type_width = self._types[base_type][0]
      return (name,delta,base_type)
  
  # return (off, width, convert_func_pair)
  def get_offset_for_name(self, name):
    parts = name.split('.')
    return self._get_offset_loop(parts)
  
  def _get_offset_loop(self, parts, base=0):
    name = parts[0]
    if not self._lookup.has_key(name):
      raise ValueError("Invalid Type key %s: %s %s" %  (self,name,self._lookup))
    num = self._lookup[name]

    type_offset = base + self._offsets[num]
    pointer = self._pointers[num]
    sub_type = self._sub_types[num]
    format = self._format[num]

    # last one
    if len(parts) == 1:
      # a pointer type -> return pointer itself
      if pointer:
        return (type_offset, 2, None)
      # a embedded sub type -> get first elemen of sub type
      elif sub_type != None:
        first_name = sub_type._format[0][1]
        return sub_type._get_offset_loop([first_name], base=type_offset)
      # a base type
      else:
        base_type = self._gen_pure_name(format[0])
        base_format = self._types[base_type]
        return (type_offset, base_format[0], base_format[1])
    # more names:
    else:
      if sub_type != None:
        return sub_type._get_offset_loop(parts[1:], base=type_offset)
      else:
        raise ValueError("Type key is no sub type: %s: %s" % (self._name,name))
  
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

  def _is_pointer(self,name):
    return name.find('*') != -1
