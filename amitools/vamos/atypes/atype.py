import re
from amitools.vamos.mem import AccessStruct


def name_convert(name):
  """convert camel case names to underscore"""
  # strip leading prefix
  pos = name.find('_')
  if pos > 0:
    name = name[pos+1:]
  # to underscore
  s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
  return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def gen_getter(cls, get_name, fname, wrap):
  if wrap:
    def getter(self):
      return wrap(self.access.r_s(fname))
  else:
    def getter(self):
      return self.access.r_s(fname)
  setattr(cls, get_name, getter)


def gen_setter(cls, set_name, fname, wrap):
  if wrap:
    def setter(self, val):
      return self.access.w_s(fname, wrap(val))
  else:
    def setter(self, val):
      return self.access.w_s(fname, val)
  setattr(cls, set_name, setter)


def AmigaType(struct_def, wrap=None, def_wrap_set=None):
  """a class decorator that automatically adds get/set methods
     for AmigaStruct fields"""
  if wrap is None:
    wrap = {}

  def deco(cls):
    # add constructor
    old_ctr = getattr(cls, "__init__", None)
    if old_ctr:
      def new_init(self, mem, addr, *args, **kwargs):
        self.mem = mem
        self.addr = addr
        self.access = AccessStruct(mem, struct_def, addr)
        old_ctr(self, *args, **kwargs)
      cls.__init__ = new_init
    else:
      def init(self, mem, addr):
        self.mem = mem
        self.addr = addr
        self.access = AccessStruct(mem, struct_def, addr)
      cls.__init__ = init

    # add generic methods
    def get_all_size(self):
      return self.access.get_size()
    cls.get_all_size = get_all_size

    def get_all_fields(self):
      return self.access.r_all()
    cls.get_all_fields = get_all_fields

    def set_all_fields(self, node):
      self.access.w_all(node)
    cls.set_all_fields = set_all_fields

    # add get/set methods
    for ftype, fname in struct_def._format:
      name = name_convert(fname)
      get_name = "get_" + name
      set_name = "set_" + name

      # c_str handling
      if ftype == "char*":
        def get_cstr(self):
          addr = self.access.r_s(fname)
          if addr == 0:
            return None
          else:
            return self.mem.r_cstr(addr)
        setattr(cls, get_name, get_cstr)
        get_name += "_addr"
        set_name += "_addr"

      # do we need to wrap a type?
      wrap_type = None
      if fname in wrap:
        wrap_type = wrap[fname]
      if name in wrap:
        wrap_type = wrap[name]

      # you can specify a wrap for get/set or
      # get only (then default is used for set)
      if wrap_type is None:
        wrap_get = None
        wrap_set = None
      elif type(wrap_type) in (list, tuple):
        wrap_get = wrap_type[0]
        wrap_set = wrap_type[1]
      else:
        wrap_get = wrap_type
        wrap_set = def_wrap_set

      # add getter
      gen_getter(cls, get_name, fname, wrap_get)
      gen_setter(cls, set_name, fname, wrap_set)

    return cls
  return deco
