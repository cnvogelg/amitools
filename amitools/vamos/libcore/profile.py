from __future__ import print_function
from amitools.vamos.log import log_prof
from amitools.vamos.profiler import Profiler
from amitools.vamos.cfgcore import ConfigDict


class LibFuncProfileData(object):
  """keep info for a library function"""

  def __init__(self, name, add_samples=False):
    self.name = name
    if add_samples:
      self.deltas = []
    else:
      self.deltas = None
    self.sum = 0.0
    self.num = 0
    self.add_samples = add_samples

  def __eq__(self, other):
    return self.name == other.name and \
        self.add_samples == other.add_samples and \
        self.deltas == other.deltas and \
        self.sum == other.sum and \
        self.num == other.num

  def __ne__(self, other):
    return self.name != other.name or \
        self.add_samples != other.add_samples or \
        self.deltas != other.deltas or \
        self.sum != other.sum or \
        self.num != other.num

  @classmethod
  def from_dict(cls, data_dict, add_samples=False):
    name = data_dict.name
    d = cls(name, add_samples)
    if 'deltas' in data_dict:
      d.deltas = data_dict.deltas
    else:
      d.deltas = None
    d.sum = data_dict.sum
    d.num = data_dict.num
    return d

  def get_data(self):
    cfg = ConfigDict({
        'name': self.name,
        'sum': self.sum,
        'num': self.num
    })
    if self.deltas is not None:
      cfg['deltas'] = self.deltas
    return cfg

  def count(self, delta):
    v = round(delta, 6)
    self.sum += v
    self.num += 1
    if self.add_samples:
      self.deltas.append(v)

  def get_name(self):
    return self.name

  def get_num_calls(self):
    return self.num

  def get_deltas(self):
    return self.deltas

  def get_sum_delta(self):
    return round(self.sum, 6)

  def get_avg_delta(self):
    if self.num > 0:
      return self.sum / self.num
    else:
      return 0.0

  def __repr__(self):
    return "LibProfileFuncData(%r,add_samples=%r):num=%r,sum=%r,deltas=%r" % \
        (self.name, self.add_samples, self.num, self.sum, self.deltas)

  def __str__(self):
    n = self.num
    s = self.sum * 1000
    a = self.get_avg_delta() * 1000
    return "%-20s  %6d calls  %10.3f ms  avg  %10.3f ms" % \
        (self.name, n, s, a)


class LibProfileData(object):
  """store call profiles of all contained functions"""

  def __init__(self, name, func_table, add_samples=False):
    """create profile with number of function indices"""
    self.name = name
    self.func_table = func_table
    self.add_samples = add_samples

  def __repr__(self):
    return "LibProfileData(%r,func_table=%r,add_samples=%r)" % \
        (self.name, self.func_table, self.add_samples)

  def __eq__(self, other):
    return self.name == other.name and \
        self.func_table == other.func_table and \
        self.add_samples == other.add_samples

  def __ne__(self, other):
    return self.name != other.name or \
        self.func_table != other.func_table or \
        self.add_samples != other.add_samples

  @classmethod
  def from_fd(cls, name, fd, add_samples=False):
    num_index = fd.get_num_indices()
    ft = []
    for i in xrange(num_index):
      func = fd.get_func_by_index(i)
      if func is None:
        ft.append(None)
      else:
        func_name = func.get_name()
        func_prof = LibFuncProfileData(func_name, add_samples)
        ft.append(func_prof)
    return cls(name, ft, add_samples)

  @classmethod
  def from_dict(cls, data_dict):
    name = data_dict.name
    add_samples = data_dict.add_samples
    funcs = data_dict.funcs
    ft = []
    for data in funcs:
      if data:
        func_prof = LibFuncProfileData.from_dict(data, add_samples)
        ft.append(func_prof)
      else:
        ft.append(None)
    return cls(name, ft, add_samples)

  def get_data(self):
    res = ConfigDict()
    res['name'] = self.name
    res['add_samples'] = self.add_samples
    funcs = []
    res['funcs'] = funcs
    for func in self.func_table:
      if func:
        data = func.get_data()
        funcs.append(data)
      else:
        funcs.append(None)
    return res

  def get_name(self):
    return self.name

  def get_func_prof(self, index):
    return self.func_table[index]

  def get_all_funcs(self):
    return self.func_table

  def get_avail_funcs(self, sort=False):
    res = []
    for func in self.func_table:
      if func and func.get_num_calls() > 0:
        res.append(func)
    if sort:
      res.sort(key=lambda x: x.name)
    return res

  def get_total(self):
    total_calls = 0
    total_delta = 0.0
    for func in self.func_table:
      if func is not None:
        total_calls += func.get_num_calls()
        total_delta += func.get_sum_delta()
    if total_calls > 0:
      avg = total_delta / total_calls
    else:
      avg = 0.0
    return total_calls, total_delta, avg

  def get_total_str(self):
    c, d, a = self.get_total()
    d *= 1000
    a *= 1000
    return "%-20s  %6d calls  %10.3f ms  avg  %10.3f ms" % \
        ("LIB TOTAL", c, d, a)

  def dump(self, write=print):
    write("----- %s -----" % self.name)
    for func in self.get_avail_funcs(True):
      if func.get_num_calls() > 0:
        write(func)
    total = self.get_total_str()
    write(total)


class LibProfiler(Profiler):

  name = "libs"

  def __init__(self, names=None, calls=False):
    self.lib_profiles = {}
    self.names = names
    self.calls = calls
    self.enabled = False

  def get_name(self):
    return self.name

  def parse_config(self, cfg):
    if not cfg:
      return True
    self.names = cfg.names
    self.calls = cfg.calls
    return True

  def set_data(self, data_dict):
    data_list = data_dict.data
    for data in data_list:
      prof = LibProfileData.from_dict(data)
      if not prof:
        return False
      name = prof.get_name()
      self.lib_profiles[name] = prof
    return True

  def get_data(self):
    res = ConfigDict()
    libs = []
    res['data'] = libs
    for name in self.lib_profiles:
      prof = self.lib_profiles[name]
      libs.append(prof.get_data())
    return res

  def setup(self):
    if self.names is None:
      self.names = []
    self.all = 'all' in self.names
    self.enabled = True
    self.all = 'all' in self.names
    log_prof.debug("libs: names=%s, all=%s, calls=%s",
                   self.names, self.all, self.calls)

  def shutdown(self):
    num_libs = self.get_num_libs()
    if num_libs == 0:
      log_prof.warn("profiling enabled but no lib profiles found!")

  def create_profile(self, lib_name, fd):
    """get or create a new profile for a library"""
    # profiling disabled
    if not self.enabled:
      log_prof.debug("libs: create '%s' -> disabled", lib_name)
      return None
    # already created profile
    if lib_name in self.lib_profiles:
      log_prof.debug("libs: create '%s' -> reuse", lib_name)
      return self.lib_profiles[lib_name]
    elif self.all or lib_name in self.names:
      # shall we create a profile for this lib?
      log_prof.debug("libs: create '%s' -> NEW", lib_name)
      prof = LibProfileData.from_fd(lib_name, fd, self.calls)
      self.lib_profiles[lib_name] = prof
      return prof
    else:
      log_prof.debug("libs: create '%s' -> not found", lib_name)

  def get_profile(self, lib_name):
    if lib_name in self.lib_profiles:
      return self.lib_profiles[lib_name]

  def get_all_lib_names(self):
    return sorted(self.lib_profiles.keys())

  def get_num_libs(self):
    return len(self.lib_profiles)

  def dump(self, log=print):
    names = self.get_all_lib_names()
    for name in names:
      prof = self.get_profile(name)
      prof.dump(log)
