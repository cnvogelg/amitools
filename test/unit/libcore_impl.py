from amitools.fd import read_lib_fd
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary
from amitools.vamos.libcore import LibImplScanner

def libcore_impl_scan_vamos_test():
  fd = read_lib_fd('vamostest.library')
  impl = VamosTestLibrary()
  # inject error func
  def PrintHello(self, ctx, wrong):
    pass
  impl.PrintHello = PrintHello.__get__(impl, impl.__class__)
  # scan impl
  scanner = LibImplScanner()
  scanner.scan(impl, fd)
  assert scanner.get_num_valid_funcs() == 4
  assert scanner.get_num_missing_funcs() == 1
  assert scanner.get_num_error_funcs() == 1
  assert scanner.get_num_invalid_funcs() == 1
  # check funcs
  missing_funcs = scanner.get_missing_funcs()
  assert missing_funcs == {
    "Dummy" : fd.get_func_by_name("Dummy")
  }
  missing_names = scanner.get_missing_func_names()
  assert missing_names == ["Dummy"]

  invalid_funcs = scanner.get_invalid_funcs()
  assert invalid_funcs == {
    "InvalidFunc" : impl.InvalidFunc
  }
  invalid_names = scanner.get_invalid_func_names()
  assert invalid_names == ["InvalidFunc"]

  error_funcs = scanner.get_error_funcs()
  assert error_funcs == {
    "PrintHello" : (fd.get_func_by_name("PrintHello"), impl.PrintHello)
  }
  error_names = scanner.get_error_func_names()
  assert error_names == ["PrintHello"]

  valid_funcs = scanner.get_valid_funcs()
  assert valid_funcs == {
    "PrintString" : (fd.get_func_by_name("PrintString"), impl.PrintString),
    "Add" : (fd.get_func_by_name("Add"), impl.Add),
    "Swap" : (fd.get_func_by_name("Swap"), impl.Swap),
    "RaiseError" : (fd.get_func_by_name("RaiseError"), impl.RaiseError)
  }
  valid_names = scanner.get_valid_func_names()
  assert valid_names == ["Add", "PrintString", "RaiseError", "Swap"]
