
def parse_scalar(val_type, val, allow_none=False):
  if type(val) is val_type:
    return val
  # none handling
  if val is None:
    if allow_none:
      return None
    else:
      raise ValueError("None not allowed for type: %s" % val_type)
  # bool special strings
  if val_type is bool:
    if type(val) is str:
      lv = val.lower()
      if lv in ("on", "true"):
        return True
      elif lv in ("off", "false"):
        return False
  return val_type(val)


class Value(object):
  def __init__(self, item_type, default=None, allow_none=None):
    self.item_type = item_type
    if allow_none is None:
      self.allow_none = item_type is str
    else:
      self.allow_none = allow_none
    if default:
      self.default = self.parse(default)
    else:
      self.default = None

  def parse(self, val):
    return parse_scalar(self.item_type, val, self.allow_none)

  def __eq__(self, other):
    return self.item_type == other.item_type and \
        self.default == other.default

  def __repr__(self):
    return "Value(%s, default=%s)" % (self.item_type, self.default)


class ValueList(object):
  def __init__(self, item_type, default=None, allow_none=None, sep=','):
    self.item_type = item_type
    self.sep = sep
    if allow_none is None:
      self.allow_none = item_type is str
    else:
      self.allow_none = allow_none
    if default:
      self.default = self.parse(default)
    else:
      self.default = None

  def parse(self, val):
    if val is None:
      return []
    elif type(val) is str:
      # split string by sep
      val = val.split(self.sep)
    elif type(val) not in (list, tuple):
      raise ValueError("expected list or tuple: %s" % val)
    # rebuild list
    res = []
    for v in val:
      r = parse_scalar(self.item_type, v, self.allow_none)
      res.append(r)
    return res

  def __eq__(self, other):
    return self.item_type == other.item_type and \
        self.default == other.default and \
        self.sep == other.sep

  def __repr__(self):
    return "ValueList(%s, default=%s, sep=%s)" % \
        (self.item_type, self.default, self.sep)


class ValueDict(object):
  def __init__(self, item_type, default=None, allow_none=None,
               sep=',', kv_sep=':'):
    self.item_type = item_type
    self.sep = sep
    self.kv_sep = kv_sep
    if allow_none is None:
      self.allow_none = item_type is str
    else:
      self.allow_none = allow_none
    if default:
      self.default = self.parse(default)
    else:
      self.default = None

  def parse(self, val):
    if val is None:
      return {}
    elif type(val) is str:
      # convert str to dict
      d = {}
      kvs = val.split(self.sep)
      for kv in kvs:
        key, val = kv.split(self.kv_sep)
        d[key] = val
      val = d
    elif type(val) is not dict:
      raise ValueError("expected dict: %s" % val)
    # rebuild dict
    res = {}
    for key in val:
      v = val[key]
      r = parse_scalar(self.item_type, v, self.allow_none)
      res[key] = r
    return res

  def __eq__(self, other):
    return self.item_type == other.item_type and \
        self.default == other.default and \
        self.sep == other.sep and \
        self.kv_sep == other.kv_sep

  def __repr__(self):
    return "ValueDict(%s, default=%s, sep=%s, kv_sep=%s)" % \
        (self.item_type, self.default, self.sep, self.kv_sep)
