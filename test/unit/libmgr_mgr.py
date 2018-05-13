import logging
import pytest
from amitools.vamos.Log import log_libmgr, log_exec
from amitools.vamos.libmgr import LibManager
from amitools.vamos.machine import Machine
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.lib.lexec.ExecLibCtx import ExecLibCtx
from amitools.vamos.lib.dos.DosLibCtx import DosLibCtx
from amitools.vamos.loader import SegmentLoader


def setup(path_mgr=None, cfg=None, profile_all=None):
  log_libmgr.setLevel(logging.INFO)
  log_exec.setLevel(logging.INFO)
  machine = Machine()
  #machine.show_instr(True)
  sp = machine.get_ram_begin() - 4
  alloc = MemoryAlloc.for_machine(machine)
  segloader = SegmentLoader(alloc)
  mgr = LibManager(machine, alloc, path_mgr, segloader,
                   cfg=cfg, profile_all=profile_all)
  # setup ctx map
  cpu = machine.get_cpu()
  mem = machine.get_mem()
  cpu_type = machine.get_cpu_type()
  exec_ctx = ExecLibCtx(machine, alloc, segloader, path_mgr)
  exec_ctx.set_lib_mgr(mgr)
  mgr.add_ctx('exec.library', exec_ctx)
  dos_ctx = DosLibCtx(machine, alloc, segloader, path_mgr, None, None)
  mgr.add_ctx('dos.library', dos_ctx)
  return machine, alloc, mgr, sp


def libmgr_mgr_bootstrap_shutdown_test():
  machine, alloc, mgr, sp = setup()
  # bootstrap exec
  exec_vlib = mgr.bootstrap_exec()
  exec_base = exec_vlib.get_addr()
  exec_lib = exec_vlib.get_library()
  # make sure exec is in place
  vmgr = mgr.vlib_mgr
  assert vmgr.get_vlib_by_name('exec.library') == exec_vlib
  assert vmgr.get_vlib_by_addr(exec_base) == exec_vlib
  assert exec_lib.open_cnt == 1
  assert machine.get_mem().r32(4) == exec_base
  # we can't expunge exec
  assert not mgr.expunge_lib(exec_base)
  # shutdown
  left = mgr.shutdown()
  assert left == 0
  # exec is now gone and mem is sane
  assert alloc.is_all_free()


def libmgr_mgr_open_vlib_test():
  machine, alloc, mgr, sp = setup()
  exec_vlib = mgr.bootstrap_exec()
  # make vamos test lib
  test_base = mgr.open_lib('vamostest.library')
  assert test_base > 0
  vmgr = mgr.vlib_mgr
  test_vlib = vmgr.get_vlib_by_addr(test_base)
  assert test_vlib
  assert vmgr.get_vlib_by_name('vamostest.library') == test_vlib
  impl = test_vlib.get_impl()
  assert impl
  assert impl.get_cnt() == 1
  lib = test_vlib.get_library()
  assert lib.version == impl.get_version()
  mgr.close_lib(test_base)
  assert impl.get_cnt() is None
  # shutdown
  left = mgr.shutdown()
  assert left == 0
  assert alloc.is_all_free()


def libmgr_mgr_open_vlib_fake_test():
  machine, alloc, mgr, sp = setup()
  exec_vlib = mgr.bootstrap_exec()
  # make vamos test lib
  test_base = mgr.open_lib('dos.library', 36, mode='fake', version=40)
  assert test_base > 0
  vmgr = mgr.vlib_mgr
  test_vlib = vmgr.get_vlib_by_addr(test_base)
  assert test_vlib
  assert vmgr.get_vlib_by_name('dos.library') == test_vlib
  impl = test_vlib.get_impl()
  assert impl is None
  lib = test_vlib.get_library()
  assert lib.version == 40
  mgr.close_lib(test_base)
  # shutdown
  left = mgr.shutdown()
  assert left == 0
  assert alloc.is_all_free()


def libmgr_mgr_open_vlib_too_new_test():
  machine, alloc, mgr, sp = setup()
  exec_vlib = mgr.bootstrap_exec()
  # make vamos test lib
  test_base = mgr.open_lib('dos.library', 41, mode='fake', version=40)
  assert test_base == 0
  # shutdown
  left = mgr.shutdown()
  assert left == 0
  assert alloc.is_all_free()


def libmgr_mgr_open_alib_test(buildlibnix):
  lib_file = buildlibnix.make_lib('testnix')

  class PathMgrMock:
    def ami_to_sys_path(self, lock, ami_path, mustExist=True):
      if ami_path == 'LIBS:testnix.library':
        return lib_file
  pm = PathMgrMock()
  machine, alloc, mgr, sp = setup(path_mgr=pm)
  exec_vlib = mgr.bootstrap_exec()
  # open fake dos.lib
  dos_base = mgr.open_lib('dos.library', mode='fake', version=40)
  # open_lib
  lib_base = mgr.open_lib("testnix.library", run_sp=sp)
  assert lib_base > 0
  amgr = mgr.alib_mgr
  assert amgr.is_lib_addr(lib_base)
  lib_info = amgr.get_lib_info_for_name("testnix.library")
  assert lib_info
  assert lib_info.is_base_addr(lib_base)
  # close lib
  seglist = mgr.close_lib(lib_base, run_sp=sp)
  assert not amgr.is_lib_addr(lib_base)
  assert seglist == 0
  lib_info = amgr.get_lib_info_for_name("testnix.library")
  assert lib_info
  assert not lib_info.is_base_addr(lib_base)
  # expunge lib
  load_addr = lib_info.get_load_addr()
  seglist = mgr.expunge_lib(load_addr, run_sp=sp)
  assert seglist > 0
  assert not amgr.is_lib_addr(lib_base)
  lib_info = amgr.get_lib_info_for_name("testnix.library")
  assert not lib_info
  # close dos
  mgr.close_lib(dos_base)
  # expunge lib
  left = mgr.shutdown(run_sp=sp)
  assert left == 0
  assert alloc.is_all_free()
