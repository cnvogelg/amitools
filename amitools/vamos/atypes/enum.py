import inspect


def EnumType(cls):
  """a class decorator that generates an enum class"""

  # collect integer vals
  _name_to_val = {}
  _val_to_name = {}
  mem = inspect.getmembers(cls)
  for name, val in mem:
    if type(val) in (int, long):
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

  def __init__(self, value):
    if type(value) is str:
      if value in self._name_to_val:
        self.value = self._name_to_val[value]
      else:
        raise ValueError("invalid value: " + value)
    else:
      self.value = value

  def __str__(self):
    return self.to_str(self.value, False)

  def __int__(self):
    return int(self.value)

  def __long__(self):
    return self.value

  def __eq__(self, other):
    return self.value == other.value

  def get_value(self):
    return self.value

  setattr(cls, '__init__', __init__)
  setattr(cls, '__str__', __str__)
  setattr(cls, '__int__', __int__)
  setattr(cls, '__long__', __long__)
  setattr(cls, '__eq__', __eq__)
  setattr(cls, 'get_value', get_value)

  return cls
