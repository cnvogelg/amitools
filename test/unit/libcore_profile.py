import StringIO
from amitools.vamos.libcore import LibProfileData, LibFuncProfileData, LibProfiler
from amitools.fd import read_lib_fd
from amitools.vamos.cfgcore import ConfigDict
from amitools.vamos.profiler import MainProfiler


def libcore_profile_func_data_test():
  func_data = LibFuncProfileData("Foo")
  assert func_data.get_name() == 'Foo'
  assert func_data.get_num_calls() == 0
  assert func_data.get_deltas() is None
  assert func_data.get_sum_delta() == 0.0
  assert func_data.get_avg_delta() == 0.0
  # count some calls
  func_data.count(1.0)
  func_data.count(2.0)
  func_data.count(3.0)
  assert func_data.get_num_calls() == 3
  assert func_data.get_deltas() is None
  assert func_data.get_sum_delta() == 6.0
  assert func_data.get_avg_delta() == 2.0
  # to/from dict
  data_dict = func_data.get_data()
  func_data2 = LibFuncProfileData.from_dict(data_dict)
  assert func_data2 == func_data
  # ne
  func_data3 = LibFuncProfileData("Bar")
  assert func_data != func_data3
  # str
  assert str(
      func_data) == "Foo                        3 calls    6000.000 ms  avg    2000.000 ms"


def libcore_profile_func_data_samples_test():
  func_data = LibFuncProfileData("Foo", True)
  assert func_data.get_name() == 'Foo'
  assert func_data.get_num_calls() == 0
  assert func_data.get_deltas() == []
  assert func_data.get_sum_delta() == 0.0
  assert func_data.get_avg_delta() == 0.0
  # count some calls
  func_data.count(1.0)
  func_data.count(2.0)
  func_data.count(3.0)
  assert func_data.get_num_calls() == 3
  assert func_data.get_deltas() == [1.0, 2.0, 3.0]
  assert func_data.get_sum_delta() == 6.0
  assert func_data.get_avg_delta() == 2.0
  # to/from dict
  data_dict = func_data.get_data()
  func_data2 = LibFuncProfileData.from_dict(data_dict, True)
  assert func_data2 == func_data
  # ne
  func_data3 = LibFuncProfileData("Foo")
  assert func_data != func_data3


def libcore_profile_data_test():
  # from fd
  name = 'dos.library'
  fd = read_lib_fd(name)
  prof = LibProfileData.from_fd(name, fd)
  # get func
  func_name = "Input"
  func = fd.get_func_by_name(func_name)
  func_prof = prof.get_func_prof(func.get_index())
  assert func_prof.get_name() == func_name
  # count
  func_prof.count(1.0)
  func_prof.count(2.0)
  func_prof.count(3.0)
  assert prof.get_total() == (3, 6.0, 2.0)
  assert prof.get_total_str() == \
      "LIB TOTAL                  3 calls    6000.000 ms" \
      "  avg    2000.000 ms"
  assert prof.get_avail_funcs() == [func_prof]
  # to/from dict
  data_dict = prof.get_data()
  prof2 = LibProfileData.from_dict(data_dict)
  assert prof == prof2
  # get func
  func_prof2 = prof2.get_func_prof(func.get_index())
  assert func_prof == func_prof2


def libcore_profile_data_samples_test():
  # from fd
  name = 'dos.library'
  fd = read_lib_fd(name)
  prof = LibProfileData.from_fd(name, fd, True)
  # get func
  func_name = "Input"
  func = fd.get_func_by_name(func_name)
  func_prof = prof.get_func_prof(func.get_index())
  assert func_prof.get_name() == func_name
  # count
  func_prof.count(1.0)
  func_prof.count(2.0)
  func_prof.count(3.0)
  assert prof.get_total() == (3, 6.0, 2.0)
  assert prof.get_total_str() == \
      "LIB TOTAL                  3 calls    6000.000 ms" \
      "  avg    2000.000 ms"
  # to/from dict
  data_dict = prof.get_data()
  prof2 = LibProfileData.from_dict(data_dict)
  assert prof == prof2
  # get func
  func_prof2 = prof2.get_func_prof(func.get_index())
  assert func_prof == func_prof2


def libcore_profile_profiler_default_test():
  name = 'dos.library'
  fd = read_lib_fd(name)
  prof = LibProfiler(names=[name])
  prof.setup()
  p = prof.create_profile(name, fd)
  assert p
  assert prof.create_profile('bla', fd) is None
  assert prof.get_profile(name) == p
  assert prof.get_num_libs() == 1
  assert prof.get_all_lib_names() == [name]
  prof.shutdown()


def libcore_profiler_profiler_set_get_data_test():
  name = 'dos.library'
  fd = read_lib_fd(name)
  prof = LibProfiler(names=[name])
  prof.setup()
  p = prof.create_profile(name, fd)
  data = prof.get_data()
  prof2 = LibProfiler()
  assert prof2.set_data(data)
  p2 = prof2.get_profile(name)
  assert p == p2


def libcore_profiler_profiler_config_test():
  name = 'dos.library'
  fd = read_lib_fd(name)
  prof = LibProfiler()
  prof.parse_config(ConfigDict({
      "names": [name],
      "calls": True
  }))
  prof.setup()
  p = prof.create_profile(name, fd)
  data = prof.get_data()
  prof2 = LibProfiler()
  assert prof2.set_data(data)
  p2 = prof2.get_profile(name)
  assert p == p2


def libcore_profiler_main_profiler_test():
  name = 'dos.library'
  fd = read_lib_fd(name)
  cfg = ConfigDict({
      "enabled": True,
      "libs": {
          "names": [name],
          "calls": True
      },
      "output": {
          "file": None,
          "append": False,
          "dump": True
      }
  })
  mp = MainProfiler()
  prof = LibProfiler()
  assert mp.parse_config(cfg)
  assert mp.add_profiler(prof)
  mp.setup()
  assert prof.names == [name]
  assert prof.calls
  p = prof.create_profile(name, fd)
  assert p
  mp.shutdown()
