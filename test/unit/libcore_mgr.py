from amitools.vamos.libcore import VLibManager, LibRegistry, LibCtxMap
from amitools.vamos.machine import Machine
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.lib.lexec.ExecLibCtx import ExecLibCtx
from amitools.vamos.lib.dos.DosLibCtx import DosLibCtx
from amitools.vamos.loader import SegmentLoader


def setup():
  machine = Machine()
  alloc = MemoryAlloc(machine.get_mem(), machine.get_ram_begin())
  mgr = VLibManager(machine, alloc)
  # setup ctx map
  cpu = machine.get_cpu()
  mem = machine.get_mem()
  cpu_type = machine.get_cpu_type()
  segloader = SegmentLoader(alloc)
  exec_ctx = ExecLibCtx(machine, alloc, segloader, None)
  mgr.add_ctx('exec.library', exec_ctx)
  return machine, alloc, mgr


def libcore_mgr_bootstrap_shutdown_test():
  machine, alloc, mgr = setup()
  # bootstrap exec
  exec_vlib = mgr.bootstrap_exec()
  exec_base = exec_vlib.get_addr()
  exec_lib = exec_vlib.get_library()
  # make sure exec is in place
  assert mgr.get_vlib_by_name('exec.library') == exec_vlib
  assert mgr.get_vlib_by_addr(exec_base) == exec_vlib
  assert exec_lib.open_cnt == 1
  assert machine.get_mem().r32(4) == exec_base
  # we can't expunge exec
  assert not mgr.expunge_lib(exec_vlib)
  # shutdown
  left = mgr.shutdown()
  assert left == 0
  # exec is now gone and mem is sane
  assert alloc.is_all_free()


def libcore_mgr_make_test():
  machine, alloc, mgr = setup()
  exec_vlib = mgr.bootstrap_exec()
  # make vamos test lib
  test_vlib = mgr.make_lib_name('vamostest.library')
  test_base = test_vlib.get_addr()
  assert test_vlib
  assert mgr.get_vlib_by_name('vamostest.library') == test_vlib
  assert mgr.get_vlib_by_addr(test_base) == test_vlib
  impl = test_vlib.get_impl()
  assert impl
  assert impl.get_cnt() == 0
  lib = test_vlib.get_library()
  assert lib.version == impl.get_version()
  # shutdown
  left = mgr.shutdown()
  assert left == 0
  assert alloc.is_all_free()


def libcore_mgr_make_version_revision_test():
  machine, alloc, mgr = setup()
  exec_vlib = mgr.bootstrap_exec()
  # make vamos test lib
  test_vlib = mgr.make_lib_name('vamostest.library', version=11, revision=23)
  test_base = test_vlib.get_addr()
  assert test_vlib
  assert mgr.get_vlib_by_name('vamostest.library') == test_vlib
  assert mgr.get_vlib_by_addr(test_base) == test_vlib
  impl = test_vlib.get_impl()
  assert impl
  assert impl.get_cnt() == 0
  lib = test_vlib.get_library()
  assert lib.version == 11
  assert lib.revision == 23
  # shutdown
  left = mgr.shutdown()
  assert left == 0
  assert alloc.is_all_free()


def libcore_mgr_make_profile_test():
  machine, alloc, mgr = setup()
  exec_vlib = mgr.bootstrap_exec()
  # make vamos test lib
  test_vlib = mgr.make_lib_name('vamostest.library', do_profile=True)
  test_base = test_vlib.get_addr()
  assert test_vlib
  assert mgr.get_vlib_by_name('vamostest.library') == test_vlib
  assert mgr.get_vlib_by_addr(test_base) == test_vlib
  impl = test_vlib.get_impl()
  assert impl
  assert impl.get_cnt() == 0
  assert test_vlib.profile
  # shutdown
  left = mgr.shutdown()
  assert left == 0
  assert alloc.is_all_free()


def libcore_mgr_make_fake_test():
  machine, alloc, mgr = setup()
  exec_vlib = mgr.bootstrap_exec()
  # make vamos test lib
  test_vlib = mgr.make_lib_name('testnix.library')
  assert test_vlib is None
  test_vlib = mgr.make_lib_name('testnix.library', allow_fake=True)
  test_base = test_vlib.get_addr()
  assert test_vlib
  assert mgr.get_vlib_by_name('testnix.library') == test_vlib
  assert mgr.get_vlib_by_addr(test_base) == test_vlib
  impl = test_vlib.get_impl()
  assert impl is None
  # shutdown
  left = mgr.shutdown()
  assert left == 0
  assert alloc.is_all_free()


def libcore_mgr_make_open_test():
  machine, alloc, mgr = setup()
  exec_vlib = mgr.bootstrap_exec()
  # make vamos test lib
  test_vlib = mgr.make_lib_name('vamostest.library')
  test_base = test_vlib.get_addr()
  impl = test_vlib.get_impl()
  lib = test_vlib.get_library()
  assert lib.version == impl.get_version()
  assert impl.get_cnt() == 0
  assert mgr.open_lib_name('vamostest.library') == test_vlib
  assert impl.get_cnt() == 1
  assert not mgr.expunge_lib(test_vlib)
  assert mgr.close_lib(test_vlib)
  assert impl.get_cnt() is None
  # shutdown
  left = mgr.shutdown()
  assert left == 0
  assert alloc.is_all_free()


def libcore_mgr_open_test():
  machine, alloc, mgr = setup()
  exec_vlib = mgr.bootstrap_exec()
  # make vamos test lib
  test_vlib = mgr.open_lib_name('vamostest.library')
  impl = test_vlib.get_impl()
  lib = test_vlib.get_library()
  assert lib.version == impl.get_version()
  assert impl.get_cnt() == 1
  assert mgr.close_lib(test_vlib)
  assert impl.get_cnt() is None
  # shutdown
  left = mgr.shutdown()
  assert left == 0
  assert alloc.is_all_free()
