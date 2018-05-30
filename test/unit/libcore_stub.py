from __future__ import print_function
import logging
import pytest

from amitools.vamos.libcore import LibStubGen, LibCtx
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary
from amitools.vamos.machine import MockMachine
from amitools.vamos.libcore import LibProfile
from amitools.fd import read_lib_fd


def _check_stub(stub):
  # check func tab
  func_tab = stub.get_func_tab()
  for f in func_tab:
    assert f is not None


def _check_profile(fd, profile):
  print_hello_func = fd.get_func_by_name('PrintHello')
  dummy_func = fd.get_func_by_name('Dummy')
  print_hello_prof = profile.get_func_prof(print_hello_func.get_index())
  dummy_func_prof = profile.get_func_prof(dummy_func.get_index())
  assert print_hello_prof.get_num_calls() == 1
  assert dummy_func_prof.get_num_calls() == 1
  profile.dump()


def _check_log(caplog):
  assert caplog.record_tuples == [
      ('valid', logging.INFO,
          '{ CALL:   30 PrintHello(  ) from PC=000000'),
      ('valid', logging.INFO,
          '} CALL: -> d0=00000000'),
      ('missing', logging.WARN,
          '? CALL:   54 Dummy( a[d0]=00000000, b[d1]=00000000 ) from PC=000000 -> d0=0 (default)'),
      ('valid', logging.INFO,
          '{ CALL:   48 Swap( a[d0]=00000000, b[d1]=00000000 ) from PC=000000'),
      ('valid', logging.INFO, '} CALL: -> d0=00000000, d1=00000000')
  ]


def _check_log_fake(caplog):
  assert caplog.record_tuples == [
      ('missing', logging.WARN,
          '? CALL:   30 PrintHello(  ) from PC=000000 -> d0=0 (default)'),
      ('missing', logging.WARN,
          '? CALL:   54 Dummy( a[d0]=00000000, b[d1]=00000000 ) from PC=000000 -> d0=0 (default)'),
      ('missing', logging.WARN,
          '? CALL:   48 Swap( a[d0]=00000000, b[d1]=00000000 ) from PC=000000 -> d0=0 (default)')
  ]


def _create_ctx():
  machine = MockMachine()
  return LibCtx(machine)


def libcore_stub_gen_base_test():
  name = 'vamostest.library'
  impl = VamosTestLibrary()
  fd = read_lib_fd(name)
  ctx = _create_ctx()
  # create stub
  gen = LibStubGen()
  stub = gen.gen_stub(name, impl, fd, ctx)
  _check_stub(stub)
  # call func
  stub.PrintHello()
  stub.Dummy()
  stub.Swap()


def libcore_stub_gen_profile_test():
  name = 'vamostest.library'
  impl = VamosTestLibrary()
  fd = read_lib_fd(name)
  ctx = _create_ctx()
  profile = LibProfile(name, fd)
  # create stub
  gen = LibStubGen()
  stub = gen.gen_stub(name, impl, fd, ctx, profile)
  _check_stub(stub)
  # call func
  stub.PrintHello()
  stub.Dummy()
  stub.Swap()
  _check_profile(fd, profile)


def libcore_stub_gen_log_test(caplog):
  caplog.set_level(logging.INFO)
  name = 'vamostest.library'
  impl = VamosTestLibrary()
  fd = read_lib_fd(name)
  ctx = _create_ctx()
  log_missing = logging.getLogger('missing')
  log_valid = logging.getLogger('valid')
  # create stub
  gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)
  stub = gen.gen_stub(name, impl, fd, ctx)
  _check_stub(stub)
  # call func
  stub.PrintHello()
  stub.Dummy()
  stub.Swap()
  _check_log(caplog)


def libcore_stub_gen_log_profile_test(caplog):
  caplog.set_level(logging.INFO)
  name = 'vamostest.library'
  impl = VamosTestLibrary()
  fd = read_lib_fd(name)
  ctx = _create_ctx()
  log_missing = logging.getLogger('missing')
  log_valid = logging.getLogger('valid')
  profile = LibProfile(name, fd)
  # create stub
  gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)
  stub = gen.gen_stub(name, impl, fd, ctx, profile)
  _check_stub(stub)
  # call func
  stub.PrintHello()
  stub.Dummy()
  stub.Swap()
  _check_log(caplog)
  _check_profile(fd, profile)


def libcore_stub_gen_exc_default_test():
  name = 'vamostest.library'
  impl = VamosTestLibrary()
  fd = read_lib_fd(name)
  ctx = _create_ctx()
  # create stub
  gen = LibStubGen()
  stub = gen.gen_stub(name, impl, fd, ctx)
  _check_stub(stub)
  # call func
  ctx.mem.w_cstr(0, 'RuntimeError')
  with pytest.raises(RuntimeError):
    stub.RaiseError()


def libcore_stub_gen_multi_arg(caplog):
  caplog.set_level(logging.INFO)
  name = 'vamostest.library'
  impl = VamosTestLibrary()
  fd = read_lib_fd(name)
  ctx = _create_ctx()
  log_missing = logging.getLogger('missing')
  log_valid = logging.getLogger('valid')
  profile = LibProfile(name, fd)
  # create stub
  gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)
  stub = gen.gen_stub(name, impl, fd, ctx, profile)
  _check_stub(stub)
  # call func
  stub.PrintHello(1, 2, a=3)
  stub.Dummy(3, b='hello')
  stub.Swap('hugo', None, c=3)
  _check_log(caplog)
  _check_profile(fd, profile)


def libcore_stub_gen_fake_base_test():
  name = 'vamostest.library'
  fd = read_lib_fd(name)
  ctx = _create_ctx()
  # create stub
  gen = LibStubGen()
  stub = gen.gen_fake_stub(name, fd, ctx)
  _check_stub(stub)
  # call func
  stub.PrintHello()
  stub.Dummy()
  stub.Swap()


def libcore_stub_gen_fake_profile_test():
  name = 'vamostest.library'
  fd = read_lib_fd(name)
  ctx = _create_ctx()
  profile = LibProfile(name, fd)
  # create stub
  gen = LibStubGen()
  stub = gen.gen_fake_stub(name, fd, ctx, profile)
  _check_stub(stub)
  # call func
  stub.PrintHello()
  stub.Dummy()
  stub.Swap()
  _check_profile(fd, profile)


def libcore_stub_gen_fake_log_test(caplog):
  caplog.set_level(logging.INFO)
  name = 'vamostest.library'
  fd = read_lib_fd(name)
  ctx = _create_ctx()
  log_missing = logging.getLogger('missing')
  log_valid = logging.getLogger('valid')
  # create stub
  gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)
  stub = gen.gen_fake_stub(name, fd, ctx)
  _check_stub(stub)
  # call func
  stub.PrintHello()
  stub.Dummy()
  stub.Swap()
  _check_log_fake(caplog)


def libcore_stub_gen_fake_log_profile_test(caplog):
  caplog.set_level(logging.INFO)
  name = 'vamostest.library'
  fd = read_lib_fd(name)
  ctx = _create_ctx()
  log_missing = logging.getLogger('missing')
  log_valid = logging.getLogger('valid')
  profile = LibProfile(name, fd)
  # create stub
  gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)
  stub = gen.gen_fake_stub(name, fd, ctx, profile)
  _check_stub(stub)
  # call func
  stub.PrintHello()
  stub.Dummy()
  stub.Swap()
  _check_log_fake(caplog)
  _check_profile(fd, profile)
