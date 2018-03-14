from amitools.fd import read_lib_fd
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary
from amitools.vamos.libcore import LibImplScanner

def libcore_impl_scan_vamos_test():
  fd = read_lib_fd('vamostest.library')
  impl = VamosTestLibrary()
  scanner = LibImplScanner()
  scanner.scan(impl, fd)
  assert scanner.get_num_valid_funcs() == 5
  assert scanner.get_num_missing_funcs() == 1
  assert scanner.get_num_error_funcs() == 0
  assert scanner.get_num_invalid_funcs() == 1
  # check funcs
  missing_funcs = scanner.get_missing_funcs()
  assert missing_funcs == {
    "Dummy" : fd.get_func_by_name("Dummy")
  }
  invalid_funcs = scanner.get_invalid_funcs()
  assert invalid_funcs == {
    "InvalidFunc" : impl.InvalidFunc
  }
  valid_funcs = scanner.get_valid_funcs()
  assert valid_funcs == {
    "PrintHello" : (fd.get_func_by_name("PrintHello"), impl.PrintHello),
    "PrintString" : (fd.get_func_by_name("PrintString"), impl.PrintString),
    "Add" : (fd.get_func_by_name("Add"), impl.Add),
    "Swap" : (fd.get_func_by_name("Swap"), impl.Swap),
    "RaiseError" : (fd.get_func_by_name("RaiseError"), impl.RaiseError)
  }
