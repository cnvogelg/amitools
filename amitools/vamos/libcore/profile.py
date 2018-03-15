from __future__ import print_function

class LibFuncProfile(object):
  """keep info for a library function"""
  def __init__(self, name, calls=0, delta=0.0):
    self.name = name
    self.calls = calls
    self.delta = delta

  def count(self, delta):
    self.calls += 1
    self.delta += delta

  def get_name(self):
    return self.name

  def get_calls(self):
    return self.calls

  def get_delta(self):
    return self.delta

  def __str__(self):
    return "%-20s: %6d calls  %10g ms" % \
      (self.name, self.calls, self.delta * 1000)


class LibProfile(object):
  """store call profiles of all contained functions"""

  def __init__(self, name, fd):
    """create profile with number of function indices"""
    self.name = name
    self.fd = fd
    # build func profile table
    self.func_table = self._build_table(fd)

  def _build_table(self, fd):
    num_index = fd.get_num_indices()
    ft = []
    for i in xrange(num_index):
      func = fd.get_func_by_index(i)
      if func is None:
        ft.append(None)
      else:
        name = func.get_name()
        func_prof = LibFuncProfile(name)
        ft.append(func_prof)
    return ft

  def get_func_prof(self, index):
    return self.func_table[index]

  def get_all_funcs(self):
    return self.func_table

  def get_avail_funcs(self, sort=False):
    res = []
    for func in self.func_table:
      if func is not None:
        res.append(func)
    if sort:
      res.sort(key=lambda x: x.name)
    return res

  def get_total(self):
    total_calls = 0
    total_delta = 0.0
    for func in self.func_table:
      if func is not None:
        total_calls += func.get_calls()
        total_delta += func.get_delta()
    return LibFuncProfile("LIB TOTAL", total_calls, total_delta)

  def dump(self, write=print):
    write("----- %s -----" % self.name)
    for func in self.get_avail_funcs(True):
      write(func)
    total = self.get_total()
    write(total)

