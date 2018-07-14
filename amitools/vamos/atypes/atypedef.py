import re
from .atype import AmigaType, AmigaTypeWithName
from .cstring import CString


class AmigaTypeDecorator(object):
  def __init__(self, struct_def, wrap, funcs, allow_struct):
    if wrap is None:
      wrap = {}
    self.struct_def = struct_def
    self.wrap = wrap
    self.funcs = funcs
    self.allow_struct = allow_struct

  def decorate(self, cls):
    name = self._validate_class(cls)
    cls._type_name = name
    # store struct def
    cls._struct_def = self.struct_def
    # add to pool
    cls._type_pool[name] = cls
    # finally create methods
    self._gen_field_methods(cls)
    # add custom functions
    if self.funcs:
      self._add_custom_funcs(cls, self.funcs)
    return cls

  def _add_custom_funcs(self, cls, funcs):
    for name in funcs:
      func = funcs[name]
      setattr(cls, name, func)

  def _validate_class(self, cls):
    # make sure cls is derived from AmigaStruct
    if cls.__bases__ != (AmigaType, ) and \
       cls.__bases__ != (AmigaTypeWithName, ):
      raise RuntimeError("cls must dervive from AmigaType")
    # get name of type
    name = self.struct_def.get_type_name()
    return name

  def _gen_field_methods(self, cls):
    # add get/set methods
    for field in self.struct_def.get_fields():
      # make a lowercase/underscore name without prefix
      # e.g. lh_TailPred -> tail_pred
      base_name = self._name_convert(field.name)

      # c_str handling
      if field.type_sig == "char*":
        self._gen_cstr_get_set(base_name, cls, field)
      # struct types
      elif field.struct_type:
        if field.is_pointer:
          self._gen_struct_ptr_get_set(base_name, cls, field)
        else:
          self._gen_struct_get(base_name, cls, field)
      # base types
      else:
        wrap_funcs = self._is_wrapped(field, base_name)
        if wrap_funcs:
          self._gen_wrap_get_set(base_name, cls, field, wrap_funcs)
        else:
          self._gen_default_get_set(base_name, cls, field)

      # common field method
      self._gen_common_field_methods(base_name, cls, field)

  def _get_gen_type(self, cls, field):
    # what type to generate for a struct field?
    gen_type = field.struct_type
    # its me -> use my type class
    if cls._struct_def == gen_type:
      return cls
    # find other type
    name = gen_type.get_type_name()
    t_type = cls.find_type(name)
    if t_type is None:
      # no type class found. can we use struct type?
      if not self.allow_struct:
        raise RuntimeError("can't find type for ptr: " + name)
    else:
      gen_type = t_type
    return gen_type

  def _gen_struct_ptr_get_set(self, base_name, cls, field):
    """access a struct pointer. return associated struct_type"""
    index = field.index
    gen_type = self._get_gen_type(cls, field)

    def get_struct_ptr(self, ptr=False):
      addr = self._struct.read_field_index(index)
      if ptr:
        return addr
      if addr == 0:
        return None
      return gen_type(self.mem, addr)

    def set_struct_ptr(self, val):
      if not type(val) is int:
        if val is None:
          val = 0
        else:
          val = val.addr
      self._struct.write_field_index(index, val)
    self._setup_get_set(base_name, cls, get_struct_ptr, set_struct_ptr)

  def _gen_struct_get(self, base_name, cls, field):
    """generate a getter for embedded structs"""
    gen_type = self._get_gen_type(cls, field)

    def get_struct(self):
      addr = self.addr + field.offset
      return gen_type(self.mem, addr)
    setattr(cls, "get_" + base_name, get_struct)

  def _is_wrapped(self, field, base_name):
    # allow field name
    if field.name in self.wrap:
      return self.wrap[field.name]
    # and converted base name
    elif base_name in self.wrap:
      return self.wrap[base_name]

  def _gen_common_field_methods(self, base_name, cls, field):
    def get_field_addr(self):
      """return the address of the field itself"""
      return self.addr + field.offset
    setattr(cls, "get_" + base_name + "_addr", get_field_addr)

  def _gen_cstr_get_set(self, base_name, cls, field):
    index = field.index

    def get_cstr(self, ptr=False):
      """return the c_str or "" if ptr==0
         or the addr of the pointer (addr=True)"""
      addr = self._struct.read_field_index(index)
      if ptr:
        return addr
      return CString(self.mem, addr)

    def set_cstr(self, val):
      """set a c_str either by address or with a CString object"""
      if type(val) is int:
        ptr = val
      elif isinstance(val, CString):
        ptr = val.get_addr()
      else:
        raise ValueError("set cstring: wrong value: %s" % val)
      self._struct.write_field_index(index, ptr)
    self._setup_get_set(base_name, cls, get_cstr, set_cstr)

  def _setup_get_set(self, base_name, cls, get_func, set_func):
    setattr(cls, "get_" + base_name, get_func)
    setattr(cls, "set_" + base_name, set_func)

  def _gen_default_get_set(self, base_name, cls, field):
    index = field.index

    def get_func(self):
      return self._struct.read_field_index(index)

    def set_func(self, val):
      self._struct.write_field_index(index, val)
    self._setup_get_set(base_name, cls, get_func, set_func)

  def _gen_wrap_get_set(self, base_name, cls, field, wrap_funcs):
    if type(wrap_funcs) in (list, tuple):
      get_wrap = wrap_funcs[0]
      set_wrap = wrap_funcs[1]
    else:
      get_wrap = wrap_funcs
      set_wrap = None

    # default conversion is integer conversion
    if set_wrap is None:
      set_wrap = int

    index = field.index
    if get_wrap:
      def get_func(self, raw=False):
        val = self._struct.read_field_index(index)
        if raw:
          return val
        return get_wrap(val)
    else:
      def get_func(self):
        return self._struct.read_field_index(index)
    if set_wrap:
      def set_func(self, val, raw=False):
        if not raw:
          val = set_wrap(val)
        self._struct.write_field_index(index, val)
    else:
      def set_func(self, val):
        self._struct.write_field_index(index, val)
    self._setup_get_set(base_name, cls, get_func, set_func)

  def _name_convert(self, name):
    """convert camel case names to underscore"""
    # strip leading prefix
    pos = name.find('_')
    if pos > 0:
      name = name[pos+1:]
    # to underscore
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def AmigaTypeDef(struct_def, wrap=None, funcs=None, allow_struct=False):
  """a class decorator that automatically adds get/set methods
     for AmigaStruct fields"""
  decorator = AmigaTypeDecorator(struct_def, wrap, funcs, allow_struct)

  def deco_func(cls):
    return decorator.decorate(cls)
  return deco_func
