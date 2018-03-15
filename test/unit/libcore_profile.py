from amitools.vamos.libcore import LibProfile, LibFuncProfile
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
  func_prof.count(1.0)
  # dump
  prof.dump()
