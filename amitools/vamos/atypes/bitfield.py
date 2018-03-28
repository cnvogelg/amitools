import inspect


def BitFieldType(cls):
  """a class decorator that generates a bit field class"""

  # collect integer vals
  _name_to_val = {}
  _val_to_name = {}
  mem = inspect.getmembers(cls)
  for name, val in mem:
    if type(val) in (int, long):
      # check that val is really a bit mask
      if val & (val - 1) != 0:
        raise ValueError("no bit mask in bit field: " % name)
      _name_to_val[name] = val
      _val_to_name[val] = name
  setattr(cls, '_name_to_val', _name_to_val)
  setattr(cls, '_val_to_name', _val_to_name)

  def to_strs(cls, val, check=True):
    res = []
    for bf_val in cls._val_to_name:
      if bf_val & val == bf_val:
        name = cls._val_to_name[bf_val]
        res.append(name)
        val &= ~bf_val
    if val != 0:
      if check:
        raise ValueError("invalid bits set: %x" % val)
      else:
        res.append(str(val))
    return res

  def to_str(cls, val, check=True):
    return "|".join(cls.to_strs(val, check))

  def from_strs(cls, *args):
    val = 0
    for name in args:
      if name in cls._name_to_val:
        bf_val = cls._name_to_val[name]
        val |= bf_val
      else:
        raise ValueError("invalid bit mask name: " + name)
    return val

  def from_str(cls, val):
    return cls.from_strs(*val.split("|"))

  def _get_bit_mask(cls, val):
    if type(val) is str:
      if val in cls._name_to_val:
        return cls._name_to_val[val]
      elif '|' in val:
        res = 0
        for v in val.split('|'):
          res |= cls._name_to_val[v]
        return res
      else:
        raise ValueError("invalid bit mask name: " + val)
    else:
      return val

  def is_set(cls, what, val):
    bmask = cls._get_bit_mask(what)
    return val & bmask == bmask

  def is_clr(cls, what, val):
    bmask = cls._get_bit_mask(what)
    return val & bmask == 0

  setattr(cls, 'to_str', classmethod(to_str))
  setattr(cls, 'from_str', classmethod(from_str))
  setattr(cls, 'to_strs', classmethod(to_strs))
  setattr(cls, 'from_strs', classmethod(from_strs))
  setattr(cls, '_get_bit_mask', classmethod(_get_bit_mask))
  setattr(cls, 'is_set', classmethod(is_set))
  setattr(cls, 'is_clr', classmethod(is_clr))

  def __init__(self, *values):
    val = 0
    for v in values:
      bmask = self._get_bit_mask(v)
      val |= bmask
    self.value = val

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
