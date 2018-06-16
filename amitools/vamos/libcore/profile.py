from __future__ import print_function
import json
from amitools.vamos.log import log_prof


class LibFuncProfile(object):
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

  def __str__(self):
    n = self.num
    s = self.sum * 1000
    a = self.get_avg_delta() * 1000
    return "%-20s  %6d calls  %10.3f ms  avg  %10.3f ms" % \
        (self.name, n, s, a)


class LibProfile(object):
  """store call profiles of all contained functions"""

  def __init__(self, name, fd, add_samples=False):
    """create profile with number of function indices"""
    self.name = name
    self.fd = fd
    self.add_samples = add_samples
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
        func_prof = LibFuncProfile(name, self.add_samples)
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

  def generate_data(self, old_data=None):
    """generate a data dictionary for JSON export"""
    func_data = {}
    if old_data and 'funcs' in old_data:
      func_data = old_data['funcs']
    # fill in my funcs
    funcs = self.get_avail_funcs()
    for f in funcs:
      num_calls = f.get_num_calls()
      if num_calls > 0:
        # at least one call was recorded
        name = f.get_name()
        deltas = f.get_deltas()
        num_calls = f.get_num_calls()
        sum_delta = f.get_sum_delta()
        # extend existing func data
        if name in func_data:
          old_func_data = func_data[name]
          old_deltas = old_func_data['deltas']
          if old_deltas is not None and deltas is not None:
            deltas = old_deltas + deltas
          num_calls += old_func_data['num_calls']
          sum_delta += round(old_func_data['sum_delta'], 6)
        # create new data
        data = {
            'num_calls': num_calls,
            'sum_delta': sum_delta,
            'deltas': deltas
        }
        func_data[name] = data
    res = {
        'funcs': func_data
    }
    return res


class LibProfilerConfig(object):
  def __init__(self, profiling=False, all_libs=False, libs=None,
               add_samples=False, file=None, append=False, dump=False):
    if libs is None:
      libs = []
    self.profiling = profiling
    self.all_libs = all_libs
    self.libs = libs
    self.add_samples = add_samples
    self.file = file
    self.append = append
    self.dump = dump

  def is_profiling(self):
    return self.profiling

  def profile_all_libs(self):
    return self.all_libs

  def profile_libs(self):
    return self.libs

  def profile_lib(self, name):
    if self.all_libs:
      return True
    return name in self.libs

  def get_add_samples(self):
    return self.add_samples

  def get_file(self):
    return self.file

  def get_file_append(self):
    return self.append

  def get_dump(self):
    return self.dump

  def __repr__(self):
    return "LibProfilerConfig(profiling=%s, all_libs=%s, libs=%s, " \
        "add_samples=%s, file=%s, append=%s, dump=%s)" % \
        (self.profiling, self.all_libs, self.libs, self.add_samples,
           self.file, self.append, self.dump)


class LibProfiler(object):
  def __init__(self, cfg=None):
    self.lib_profiles = {}
    self.cfg = cfg

  def shutdown(self):
    """dump or save file"""
    if self.cfg and self.cfg.is_profiling():
      num_libs = self.get_num_libs()
      if num_libs == 0:
        log_prof.warn("profiling enabled but no lib profiles found!")
      else:
        # save file
        file = self.cfg.get_file()
        if file:
          append = self.cfg.get_file_append()
          log_prof.info("writing %d lib profiles to '%s' (append=%s)",
                        num_libs, file, append)
          self.save_json_file(file, append)
        # dump
        if self.cfg.get_dump():
          self.dump(log_prof.info)

  def create_profile(self, lib_name, fd):
    """get or create a new profile for a library"""
    # profiling disabled
    if not self.cfg or not self.cfg.is_profiling():
      return None
    # already created profile
    if lib_name in self.lib_profiles:
      return self.lib_profiles[lib_name]
    elif self.cfg.profile_lib(lib_name):
      # shall we create a profile for this lib?
      prof = LibProfile(lib_name, fd, self.cfg.get_add_samples())
      self.lib_profiles[lib_name] = prof
      return prof

  def get_profile(self, lib_name):
    if lib_name in self.lib_profiles:
      return self.lib_profiles[lib_name]

  def get_all_lib_names(self):
    return sorted(self.lib_profiles.keys())

  def get_num_libs(self):
    return len(self.lib_profiles)

  def save_json_file(self, name, append=False):
    # read existing json file
    old_data = None
    if append:
      with open(name, "r") as fh:
        old_data = json.load(fh)
    with open(name, "w") as fh:
      self.save_json_fobj(fh, old_data)

  def save_json_fobj(self, fobj, data=None):
    data = self.generate_data(data)
    json.dump(data, fobj, sort_keys=True)

  def generate_data(self, data=None):
    if data is None:
      data = {}
    names = self.get_all_lib_names()
    for name in names:
      prof = self.get_profile(name)
      if name in data:
        old_data = data[name]
      else:
        old_data = None
      data[name] = prof.generate_data(old_data)
    return data

  def dump(self, write=print):
    names = self.get_all_lib_names()
    for name in names:
      prof = self.get_profile(name)
      prof.dump(write)
