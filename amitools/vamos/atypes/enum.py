import inspect


def EnumType(cls):
  """a class decorator that generates an enum class"""

  # collect integer vals
  _name_to_val = {}
  _val_to_name = {}
  mem = inspect.getmembers(cls)
  for name, val in mem:
    if type(val) is int:
      _name_to_val[name] = val
      _val_to_name[val] = name
  setattr(cls, '_name_to_val', _name_to_val)
  setattr(cls, '_val_to_name', _val_to_name)

  def to_str(cls, val, check=True):
    if val in cls._val_to_name:
      return cls._val_to_name[val]
    if check:
      raise ValueError("%s is an unknown Enum value" % val)
    else:
      return str(val)

  def from_str(cls, name):
    if name in cls._name_to_val:
      return cls._name_to_val[name]
    raise ValueError("'%s' is an unknown Enum string" % name)

  setattr(cls, 'to_str', classmethod(to_str))
  setattr(cls, 'from_str', classmethod(from_str))
  return cls
