import pytest

from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.ExecLibrary import ExecLibrary
from amitools.vamos.libcore import LibRegistry
from amitools.vamos.error import VamosInternalError

def lib_reg_find_cls_test():
  lr = LibRegistry()
  assert lr.find_cls_by_name('dos.library') is DosLibrary
  assert lr.find_cls_by_name('exec.library') is ExecLibrary

def lib_reg_has_name_test():
  lr = LibRegistry()
  assert lr.has_name('dos.library')
  assert lr.has_name('exec.library')

def lib_reg_get_all_cls_test():
  lr = LibRegistry()
  all_cls = lr.get_all_cls()
  assert DosLibrary in all_cls
  assert ExecLibrary in all_cls

def lib_reg_get_all_names_test():
  lr = LibRegistry()
  all_cls = lr.get_all_names()
  assert 'dos.library' in all_cls
  assert 'exec.library' in all_cls

def lib_reg_open_test():
  lr = LibRegistry()
  lib = lr.open_lib('dos.library')
  assert lib is not None
  # double open fails
  with pytest.raises(VamosInternalError):
    lib = lr.open_lib('dos.library')
  assert lr.has_open_libs()
  assert lr.get_open_libs() == [lib]
  lr.close_lib('dos.library')
  # double close fails
  with pytest.raises(VamosInternalError):
    lib = lr.close_lib('dos.library')
  assert not lr.has_open_libs()
  assert lr.get_open_libs() == []

def lib_reg_fake_open_test():
  lr = LibRegistry()
  lib = lr.open_fake_lib('fake.library')
  assert lib is not None
  # double open fails
  with pytest.raises(VamosInternalError):
    lib = lr.open_fake_lib('fake.library')
  assert lr.has_open_libs()
  assert lr.get_open_libs() == [lib]
  lr.close_lib('fake.library')
  # double close fails
  with pytest.raises(VamosInternalError):
    lib = lr.close_lib('fake.library')
  assert not lr.has_open_libs()
  assert lr.get_open_libs() == []

def lib_reg_open_all_test():
  lr = LibRegistry()
  all_names = lr.get_all_names()
  for name in all_names:
    lr.open_lib(name)
    lr.close_lib(name)
