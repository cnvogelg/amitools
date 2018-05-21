import StringIO
from amitools.vamos.libcore import LibProfile, LibFuncProfile, LibProfiler
from amitools.fd import read_lib_fd


def libcore_profile_test():
  name = 'vamostest.library'
  fd = read_lib_fd(name)
  prof = LibProfile(name, fd)
  # func
  func_name = "Add"
  func = fd.get_func_by_name(func_name)
  func_prof = prof.get_func_prof(func.get_index())
  assert func_prof.get_name() == func_name
  # count
  func_prof.count(1.0)
  func_prof.count(2.0)
  func_prof.count(3.0)
  assert func_prof.get_num_calls() == 3
  assert func_prof.get_deltas() is None
  assert func_prof.get_sum_delta() == 6.0
  assert func_prof.get_avg_delta() == 2.0
  assert str(
      func_prof) == "Add                        3 calls    6000.000 ms  avg    2000.000 ms"
  # dump
  assert prof.get_total() == (3, 6.0, 2.0)
  assert prof.get_total_str(
  ) == "LIB TOTAL                  3 calls    6000.000 ms  avg    2000.000 ms"
  prof.dump()


def libcore_profile_samples_test():
  name = 'vamostest.library'
  fd = read_lib_fd(name)
  prof = LibProfile(name, fd, True)
  # func
  func_name = "Add"
  func = fd.get_func_by_name(func_name)
  func_prof = prof.get_func_prof(func.get_index())
  assert func_prof.get_name() == func_name
  # count
  func_prof.count(1.0)
  func_prof.count(2.0)
  func_prof.count(3.0)
  assert func_prof.get_num_calls() == 3
  assert func_prof.get_deltas() == [1.0, 2.0, 3.0]
  assert func_prof.get_sum_delta() == 6.0
  assert func_prof.get_avg_delta() == 2.0
  assert str(
      func_prof) == "Add                        3 calls    6000.000 ms  avg    2000.000 ms"
  # dump
  assert prof.get_total() == (3, 6.0, 2.0)
  assert prof.get_total_str(
  ) == "LIB TOTAL                  3 calls    6000.000 ms  avg    2000.000 ms"
  prof.dump()


def libcore_profile_profiler_test():
  name = 'vamostest.library'
  fd = read_lib_fd(name)
  p = LibProfiler()
  assert not p.get_profile(name)
  prof = p.add_profile(name, fd)
  assert prof
  assert prof == p.get_profile(name)
  assert p.get_all_lib_names() == [name]
  assert p.get_num_libs() == 1


def gen_prof(add_samples=False):
  name = 'vamostest.library'
  fd = read_lib_fd(name)
  p = LibProfiler(add_samples)
  lp = p.add_profile(name, fd)
  # get func
  func_name = "Add"
  func = fd.get_func_by_name(func_name)
  fp = lp.get_func_prof(func.get_index())
  fp.count(1.0)
  fp.count(2.0)
  fp.count(3.0)
  return p, lp, fp


def libcore_profile_gen_data_test():
  p, lp, fp = gen_prof()
  data = p.generate_data()
  assert data == {
      'vamostest.library': {
          'funcs': {'Add':
                    {'deltas': None,
                     'num_calls': 3,
                     'sum_delta': 6.0}}}}


def libcore_profile_gen_data_samples_test():
  p, lp, fp = gen_prof(True)
  data = p.generate_data()
  assert data == {
      'vamostest.library': {
          'funcs': {'Add':
                    {'deltas': [1.0, 2.0, 3.0],
                     'num_calls': 3,
                     'sum_delta': 6.0}}}}


def libcore_profile_gen_data_old_test():
  p, lp, fp = gen_prof()
  old_data = {
      'vamostest.library': {
          'funcs': {'Add':
                    {'deltas': [1.0, 2.0, 3.0],
                     'num_calls': 3,
                     'sum_delta': 6.0}}}}
  data = p.generate_data(old_data)
  assert data == {
      'vamostest.library': {
          'funcs': {'Add':
                    {'deltas': None,
                     'num_calls': 6,
                     'sum_delta': 12.0}}}}


def libcore_profile_gen_data_samples_old_test():
  p, lp, fp = gen_prof(True)
  old_data = {
      'vamostest.library': {
          'funcs': {'Add':
                    {'deltas': [1.0, 2.0, 3.0],
                     'num_calls': 3,
                     'sum_delta': 6.0}}}}
  data = p.generate_data(old_data)
  assert data == {
      'vamostest.library': {
          'funcs': {'Add':
                    {'deltas': [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
                     'num_calls': 6,
                     'sum_delta': 12.0}}}}
