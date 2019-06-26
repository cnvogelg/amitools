import inspect
from amitools.vamos.astructs import LibraryStruct
from amitools.vamos.error import VamosInternalError


class LibImpl(object):
  """base class for all Python-based library implementations"""

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


class LibImplScan(object):
  """scan result of a vamos library implementation

     it contains extracted function lists"""

  TAG_VALID = "valid"
  TAG_ERROR = "error"
  TAG_INVALID = "invalid"
  TAG_MISSING = "missing"

  def __init__(self, name, impl, fd):
    self.name = name
    self.impl = impl
    self.fd = fd
    self.valid_funcs = {}
    self.missing_funcs = {}
    self.invalid_funcs = {}
    self.error_funcs = {}
    self.func_tags = {}

  def get_name(self):
    return self.name

  def get_impl(self):
    return self.impl

  def get_fd(self):
    return self.fd

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

  def get_func_tags(self):
    """return a map of name -> tag"""
    return self.func_tags


class LibImplScanner(object):
  """scan an implementation of a library for functions"""

  def scan(self, name, impl, fd, inc_std_funcs=False):
    """scan a library implementation with a functable"""
    res = LibImplScan(name, impl, fd)
    found_names = []
    members = inspect.getmembers(impl, predicate=inspect.ismethod)
    for name, method in members:
      tag = None
      # is a func in the fd?
      if fd.has_func(name):
        func = fd.get_func_by_name(name)
        if self._check_argspec(method):
          res.valid_funcs[name] = (func, method)
          tag = LibImplScan.TAG_VALID
        else:
          res.error_funcs[name] = (func, method)
          tag = LibImplScan.TAG_ERROR
        found_names.append(name)
      # not a func name
      else:
        # if name is camel case then it is invalid
        if name[0].isupper():
          res.invalid_funcs[name] = method
          tag = LibImplScan.TAG_INVALID
      # store func tag
      if tag:
        res.func_tags[name] = tag
    # now check for missing functions
    funcs = fd.get_funcs()
    if len(funcs) != len(found_names):
      for func in funcs:
        # skip std functions
        if inc_std_funcs or not func.is_std():
          name = func.get_name()
          if name not in found_names:
            res.missing_funcs[name] = func
            res.func_tags[name] = LibImplScan.TAG_MISSING
    # return scan result
    return res

  def scan_checked(self, name, impl, fd, inc_std_funcs=False, ignore_invalid=False):
    res = self.scan(name, impl, fd, inc_std_funcs)
    # raise an error if impl is not valid
    num_invalid = res.get_num_invalid_funcs()
    num_error = res.get_num_error_funcs()
    if num_invalid > 0 and not ignore_invalid:
      names = res.get_invalid_func_names()
      txt = ",".join(names)
      raise VamosInternalError(
          "'%s' impl has %d invalid funcs: %s" % (name, num_invalid, txt))
    if num_error > 0:
      names = res.get_error_func_names()
      txt = ",".join(names)
      raise VamosInternalError(
          "'%s' impl has %d error funcs: %s" % (name, num_error, txt))

  def _check_argspec(self, method):
    fas = inspect.getfullargspec(method)
    if fas.varargs is not None:
      return False
    if fas.varkw is not None:
      return False
    if fas.defaults is not None:
      return False
    return fas.args == ['self', 'ctx']
