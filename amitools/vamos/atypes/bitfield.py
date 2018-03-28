import inspect


def BitFieldType(cls):
  """a class decorator that generates a bit field class"""

  # collect integer vals
  _name_to_val = {}
  _val_to_name = {}
  mem = inspect.getmembers(cls)
  for name, val in mem:
    if type(val) is int:
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

  def from_strs(cls, *args):
    val = 0
    for name in args:
      if name in cls._name_to_val:
        bf_val = cls._name_to_val[name]
        val |= bf_val
      else:
        raise ValueError("invalid bit mask name: " + name)
    return val

  def _get_bit_mask(cls, val):
    if type(val) is str:
      if val in cls._name_to_val:
        return cls._name_to_val[val]
      else:
        raise ValueError("invalid bit mask name: " + val)
    else:
      if val in cls._val_to_name:
        return val
      else:
        raise ValueError("invalid bti mask value: " + val)

  def is_set(cls, what, val):
    bmask = cls._get_bit_mask(what)
    return val & bmask == bmask

  def is_clr(cls, what, val):
    bmask = cls._get_bit_mask(what)
    return val & bmask == 0

  setattr(cls, 'to_strs', classmethod(to_strs))
  setattr(cls, 'from_strs', classmethod(from_strs))
  setattr(cls, '_get_bit_mask', classmethod(_get_bit_mask))
  setattr(cls, 'is_set', classmethod(is_set))
  setattr(cls, 'is_clr', classmethod(is_clr))
  return cls
