
class Argument(object):
  def __init__(self, *args, **kwargs):
    self.args = args
    self.kwargs = kwargs
    self.arg = None

  def __repr__(self):
    return "Argument(%s, %s)" % (self.args, self.kwargs)

  def add(self, parser):
    self.arg = parser.add_argument(*self.args, **self.kwargs)

  def get_value(self, args):
    return getattr(args, self.arg.dest)


class ArgumentDict(object):
  def __init__(self, arg_dict=None):
    if arg_dict is None:
      arg_dict = {}
    self._check_dict(arg_dict)
    self.arg_dict = arg_dict

  def get_cfg(self):
    return self.arg_dict

  def add_args(self, parser, arg_dict=None):
    if arg_dict is None:
      arg_dict = self.arg_dict
    for key in arg_dict:
      val = arg_dict[key]
      vtype = type(val)
      if vtype is dict:
        self.add_args(parser, val)
      else:
        val.add(parser)

  def gen_dict(self, args, arg_dict=None, skip_none=True):
    if arg_dict is None:
      arg_dict = self.arg_dict
    res = {}
    for key in arg_dict:
      val = arg_dict[key]
      vtype = type(val)
      if vtype is dict:
        res_val = self.gen_dict(args, val)
        res[key] = res_val
      else:
        res_val = val.get_value(args)
        if res_val is not None or not skip_none:
          res[key] = res_val
    return res

  def _check_dict(self, arg_dict):
    for key in arg_dict:
      val = arg_dict[key]
      vtype = type(val)
      if vtype is dict:
        self._check_dict(val)
      elif vtype is not Argument:
        raise ValueError("invalid type in arg dict: %s", val)
