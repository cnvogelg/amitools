import inspect
from amitools.vamos.astructs import LibraryStruct


class LibImpl(object):
  """base class for all Python-based library implementations"""

  def is_base_lib(self):
    return False

  def get_struct_def(self):
    """return the structure of your library pos_size"""
    return LibraryStruct

  def get_version(self):
    return 40

  def setup_lib(self, ctx, base_addr):
    pass

  def finish_lib(self, ctx):
    pass

  def open_lib(self, ctx, open_cnt):
    pass

  def close_lib(self, ctx, open_cnt):
    pass


class LibImplScanner(object):
  """scan a vamos library implementation and extract function lists"""

  def __init__(self, inc_std_funcs=False):
    self._reset()
    self.inc_std_funcs = inc_std_funcs

  def _reset(self):
    self.valid_funcs = {}
    self.missing_funcs = {}
    self.invalid_funcs = {}
    self.error_funcs = {}

  def get_valid_funcs(self):
    """return map: name -> (fd_func, method)"""
    return self.valid_funcs

  def get_missing_funcs(self):
    """return map: name -> fd_func"""
    return self.missing_funcs

  def get_invalid_funcs(self):
    """return map: name -> method"""
    return self.invalid_funcs

  def get_error_funcs(self):
    """return map: name -> (fd_func, method)"""
    return self.error_funcs

  def get_valid_func_names(self):
    return sorted(self.valid_funcs.keys())

  def get_missing_func_names(self):
    return sorted(self.missing_funcs.keys())

  def get_invalid_func_names(self):
    return sorted(self.invalid_funcs.keys())

  def get_error_func_names(self):
    return sorted(self.error_funcs.keys())

  def get_num_valid_funcs(self):
    return len(self.valid_funcs)

  def get_num_missing_funcs(self):
    return len(self.missing_funcs)

  def get_num_invalid_funcs(self):
    return len(self.invalid_funcs)

  def get_num_error_funcs(self):
    return len(self.error_funcs)

  def _check_argspec(self, method):
    (args, varargs, keywords, defaults) = inspect.getargspec(method)
    if varargs is not None:
      return False
    if keywords is not None:
      return False
    if defaults is not None:
      return False
    return args == ['self', 'ctx']

  def scan(self, impl, fd):
    """scan a library implementation with a functable"""
    self._reset()
    found_names = []
    members = inspect.getmembers(impl, predicate=inspect.ismethod)
    for name, method in members:
      # is a func in the fd?
      if fd.has_func(name):
        func = fd.get_func_by_name(name)
        if self._check_argspec(method):
          self.valid_funcs[name] = (func, method)
        else:
          self.error_funcs[name] = (func, method)
        found_names.append(name)
      # not a func name
      else:
        # if name is camel case then it is invalid
        if name[0].isupper():
          self.invalid_funcs[name] = method
    # now check for missing functions
    funcs = fd.get_funcs()
    if len(funcs) != len(found_names):
      for func in funcs:
        # skip std functions
        if self.inc_std_funcs or not func.is_std():
          name = func.get_name()
          if name not in found_names:
            self.missing_funcs[name] = func
