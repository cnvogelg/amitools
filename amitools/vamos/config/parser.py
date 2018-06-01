import logging
from .value import Value, ValueList, ValueDict


log_cfg = logging.getLogger('config')


class Parser(object):

  def __init__(self, default=None):
    if default is None:
      default = {}
    self._check_default_cfg(default)
    self.default = {}
    self._gen_default_cfg(default, self.default)
    self.cfg = self._gen_default_dict(self.default)

  def get_default_cfg(self):
    return self.default

  def get_cfg_dict(self):
    return self.cfg

  def setup_args(self, main, argparse):
    # needs to be customized in derived class
    pass

  def parse_args(self, main, args):
    # needs to be customized in derived class
    pass

  def parse_ini_config(self, main, cfg_dict):
    self._merge_cfg(self.cfg, cfg_dict, self.default)

  def parse_dict_config(self, main, cfg_dict):
    self._merge_cfg(self.cfg, cfg_dict, self.default)

  def _merge_cfg(self, mine, other, default):
    for key in other:
      if key in default:
        self._merge_cfg_key(self, mine, other, default, key)

  def _merge_cfg_key(self, mine, other, default, key, def_key=None):
    if def_key is None:
      def_key = key
    oval = other[key]
    dval = default[def_key]
    mval = mine[key]
    if type(dval) is dict:
      # create dict if missing
      if key not in mine:
        mine[key] = {}
      # recurse in dict
      if type(oval) is not dict:
        raise ValueError("expected dict key: %s" % key)
      self._merge_cfg(mval, oval, dval)
    else:
      # overwrite my key
      mine[key] = dval.parse(oval)

  def _check_default_cfg(self, cfg):
    t = type(cfg)
    if t in (bool, str, int, Value, ValueList, ValueDict):
      pass
    elif t is dict:
      for key in cfg:
        v = cfg[key]
        self._check_default_cfg(v)
    else:
      raise ValueError("invalid config type: %s for %s" % (t, cfg))

  def _gen_default_cfg(self, in_cfg, out_cfg):
    for key in in_cfg:
      val = in_cfg[key]
      t = type(val)
      if t in (bool, int, str):
        # auto wrap in Value
        out_cfg[key] = Value(t, val)
      elif t is dict:
        new_dict = {}
        out_cfg[key] = new_dict
        self._gen_default_cfg(val, new_dict)
      elif t in (Value, ValueList, ValueDict):
        out_cfg[key] = val
      else:
        raise ValueError("invalid type in default config: %s" % val)

  def _gen_default_dict(self, def_cfg):
    res = {}
    for key in def_cfg:
      val = def_cfg[key]
      if type(val) is dict:
        res[key] = self._gen_default_dict(val)
      else:
        res[key] = val.default
    return res
