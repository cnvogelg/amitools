import logging
import pytest
from amitools.vamos.log import log_libmgr, log_exec
from amitools.vamos.libcore import LibCtx
from amitools.vamos.libmgr import LibManager, LibMgrCfg, LibCfg
from amitools.vamos.machine import Machine
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.lib.lexec.ExecLibCtx import ExecLibCtx
from amitools.vamos.lib.dos.DosLibCtx import DosLibCtx
from amitools.vamos.lib.ExecLibrary import ExecLibrary
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary
from amitools.vamos.lib.VamosTestDevice import VamosTestDevice
from amitools.vamos.loader import SegmentLoader


def setup(path_mgr=None):
    log_libmgr.setLevel(logging.INFO)
    log_exec.setLevel(logging.INFO)
    machine = Machine()
    # machine.show_instr(True)
    sp = machine.get_ram_begin() - 4
    alloc = MemoryAlloc.for_machine(machine)
    segloader = SegmentLoader(alloc, path_mgr)
    cfg = LibMgrCfg()
    mgr = LibManager(machine, alloc, segloader, cfg)
    # setup ctx map
    cpu = machine.get_cpu()
    mem = machine.get_mem()
    cpu_type = machine.get_cpu_type()
    exec_ctx = ExecLibCtx(machine, alloc, segloader, path_mgr, mgr)
    mgr.add_ctx("exec.library", exec_ctx)
    mgr.add_impl_cls("exec.library", ExecLibrary)
    dos_ctx = DosLibCtx(machine, alloc, segloader, path_mgr, None, None)
    mgr.add_ctx("dos.library", dos_ctx)
    mgr.add_impl_cls("dos.library", DosLibrary)
    mgr.add_impl_cls("vamostest.library", VamosTestLibrary)
    mgr.add_impl_cls("vamostestdev.device", VamosTestDevice)
    return machine, alloc, mgr, sp, cfg


def libmgr_mgr_bootstrap_shutdown_test():
    machine, alloc, mgr, sp, cfg = setup()
    # bootstrap exec
    exec_vlib = mgr.bootstrap_exec()
    exec_base = exec_vlib.get_addr()
    exec_lib = exec_vlib.get_library()
    # make sure exec is in place
    vmgr = mgr.vlib_mgr
    assert vmgr.get_vlib_by_name("exec.library") == exec_vlib
    assert vmgr.get_vlib_by_addr(exec_base) == exec_vlib
    assert exec_vlib.get_ctx() == vmgr.ctx_map["exec.library"]
    assert exec_lib.open_cnt.val == 1
    assert machine.get_mem().r32(4) == exec_base
    # we can't expunge exec
    assert not mgr.expunge_lib(exec_base)
    # check proxy for exec
    exec_proxy = mgr.get_lib_proxy_mgr().get_exec_lib_proxy()
    mem_addr = exec_proxy.AllocMem(128, 0)
    assert mem_addr
    exec_proxy.FreeMem(mem_addr, 128)
    # check proxy for exec in ctx
    exec_proxy = exec_vlib.ctx.proxies.get_exec_lib_proxy()
    mem_addr = exec_proxy.AllocMem(128, 0)
    assert mem_addr
    exec_proxy.FreeMem(mem_addr, 128)
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    # exec is now gone and mem is sane
    assert alloc.is_all_free()


def libmgr_mgr_open_fail_test():
    class PathMgrMock:
        def ami_to_sys_path(self, lock, ami_path, mustExist=True):
            return None

    pm = PathMgrMock()
    machine, alloc, mgr, sp, cfg = setup(path_mgr=pm)
    mgr.bootstrap_exec()
    # open non-existing lib
    lib_base = mgr.open_lib("blubber.library")
    assert lib_base == 0
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    # exec is now gone and mem is sane
    assert alloc.is_all_free()


def libmgr_mgr_open_vlib_test():
    machine, alloc, mgr, sp, cfg = setup()
    exec_vlib = mgr.bootstrap_exec()
    # make vamos test lib
    test_base = mgr.open_lib("vamostest.library")
    assert test_base > 0
    vmgr = mgr.vlib_mgr
    test_vlib = vmgr.get_vlib_by_addr(test_base)
    assert test_vlib
    assert type(test_vlib.get_ctx()) == LibCtx
    assert vmgr.get_vlib_by_name("vamostest.library") == test_vlib
    impl = test_vlib.get_impl()
    assert impl
    assert impl.get_cnt() == 1
    lib = test_vlib.get_library()
    assert lib.version.val == impl.get_version()
    mgr.close_lib(test_base)
    assert impl.get_cnt() is None
    # try to open a proxy
    proxy_mgr = mgr.get_lib_proxy_mgr()
    proxy = proxy_mgr.open_lib_proxy("vamostest.library")
    assert proxy
    assert proxy.Add(2, 3) == 5
    proxy_mgr.close_lib_proxy(proxy)
    # try to open a proxy directly in ctx
    proxy_mgr = test_vlib.ctx.proxies
    proxy = proxy_mgr.open_lib_proxy("vamostest.library")
    assert proxy
    assert proxy.Add(2, 3) == 5
    proxy_mgr.close_lib_proxy(proxy)
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()


def libmgr_mgr_open_vlib_dev_test():
    machine, alloc, mgr, sp, cfg = setup()
    exec_vlib = mgr.bootstrap_exec()
    # make vamos test lib
    test_base = mgr.open_lib("vamostestdev.device")
    assert test_base > 0
    vmgr = mgr.vlib_mgr
    test_vlib = vmgr.get_vlib_by_addr(test_base)
    assert test_vlib
    assert type(test_vlib.get_ctx()) == LibCtx
    assert vmgr.get_vlib_by_name("vamostestdev.device") == test_vlib
    impl = test_vlib.get_impl()
    assert impl
    assert impl.get_cnt() == 1
    lib = test_vlib.get_library()
    assert lib.version.val == impl.get_version()
    mgr.close_lib(test_base)
    assert impl.get_cnt() is None
    # try to open a proxy
    proxy_mgr = mgr.get_lib_proxy_mgr()
    proxy = proxy_mgr.open_lib_proxy("vamostestdev.device")
    assert proxy
    assert proxy.Add(1, 2) == 3
    proxy_mgr.close_lib_proxy(proxy)
    # try to open a proxy directly in ctx
    proxy_mgr = test_vlib.ctx.proxies
    proxy = proxy_mgr.open_lib_proxy("vamostestdev.device")
    assert proxy
    assert proxy.Add(1, 2) == 3
    proxy_mgr.close_lib_proxy(proxy)
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()


def libmgr_mgr_open_vlib_fake_fd_test():
    machine, alloc, mgr, sp, cfg = setup()
    exec_vlib = mgr.bootstrap_exec()
    # make vamos test lib
    cfg.add_lib_cfg(
        "dos.library", LibCfg(create_mode=LibCfg.CREATE_MODE_FAKE, force_version=40)
    )
    test_base = mgr.open_lib("dos.library", 36)
    assert test_base > 0
    vmgr = mgr.vlib_mgr
    test_vlib = vmgr.get_vlib_by_addr(test_base)
    assert test_vlib
    assert vmgr.get_vlib_by_name("dos.library") == test_vlib
    impl = test_vlib.get_impl()
    assert impl is None
    lib = test_vlib.get_library()
    assert lib.version.val == 40
    mgr.close_lib(test_base)
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()


def libmgr_mgr_open_vlib_fake_no_fd_test():
    machine, alloc, mgr, sp, cfg = setup()
    exec_vlib = mgr.bootstrap_exec()
    # make vamos test lib
    cfg.add_lib_cfg(
        "foo.library",
        LibCfg(
            create_mode=LibCfg.CREATE_MODE_FAKE, force_version=40, num_fake_funcs=10
        ),
    )
    test_base = mgr.open_lib("foo.library", 36)
    assert test_base > 0
    vmgr = mgr.vlib_mgr
    test_vlib = vmgr.get_vlib_by_addr(test_base)
    assert test_vlib
    assert vmgr.get_vlib_by_name("foo.library") == test_vlib
    impl = test_vlib.get_impl()
    assert impl is None
    lib = test_vlib.get_library()
    assert lib.version.val == 40
    assert lib.neg_size.val == 68
    mgr.close_lib(test_base)
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()


def libmgr_mgr_open_vlib_too_new_test():
    machine, alloc, mgr, sp, cfg = setup()
    exec_vlib = mgr.bootstrap_exec()
    # make vamos test lib
    cfg.add_lib_cfg(
        "dos.library", LibCfg(create_mode=LibCfg.CREATE_MODE_FAKE, force_version=40)
    )
    test_base = mgr.open_lib("dos.library", 41)
    assert test_base == 0
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()


class ALibHelper(object):
    def __init__(self, lib_file, lib_name):
        class PathMgrMock:
            def ami_to_sys_path(self, lock, ami_path, mustExist=True):
                if ami_path == "LIBS:" + lib_name:
                    return lib_file

        pm = PathMgrMock()
        self.machine, self.alloc, self.mgr, self.sp, self.cfg = setup(path_mgr=pm)
        self.mgr.bootstrap_exec()
        self.cfg.add_lib_cfg(
            "dos.library", LibCfg(create_mode=LibCfg.CREATE_MODE_FAKE, force_version=40)
        )
        self.dos_base = self.mgr.open_lib("dos.library")

    def shutdown(self):
        # close dos
        self.mgr.close_lib(self.dos_base)
        # expunge lib
        left = self.mgr.shutdown(run_sp=self.sp)
        assert left == 0
        assert self.alloc.is_all_free()


def open_alib(lib_file, lib_name, ok=True, version=0, mode=None):
    h = ALibHelper(lib_file, lib_name)
    mgr = h.mgr
    # setup config
    if mode:
        h.cfg.add_lib_cfg(lib_name, LibCfg(create_mode=mode))
    # open_lib
    lib_base = mgr.open_lib(lib_name, run_sp=h.sp, version=version)
    if not ok:
        assert lib_base == 0
        h.shutdown()
        return
    assert lib_base > 0
    amgr = mgr.alib_mgr
    assert amgr.is_base_addr(lib_base)
    lib_info = amgr.get_lib_info_for_name(lib_name)
    assert lib_info
    assert lib_info.is_base_addr(lib_base)
    # close lib
    seglist = mgr.close_lib(lib_base, run_sp=h.sp)
    assert not amgr.is_base_addr(lib_base)
    assert seglist == 0
    lib_info = amgr.get_lib_info_for_name(lib_name)
    assert lib_info
    assert not lib_info.is_base_addr(lib_base)
    # expunge lib
    load_addr = lib_info.get_load_addr()
    seglist = mgr.expunge_lib(load_addr, run_sp=h.sp)
    assert seglist > 0
    assert not amgr.is_load_addr(lib_base)
    lib_info = amgr.get_lib_info_for_name(lib_name)
    assert not lib_info
    # proxy
    proxy_mgr = mgr.get_lib_proxy_mgr()
    proxy = proxy_mgr.open_lib_proxy(lib_name, run_sp=h.sp)
    assert proxy
    assert proxy.Add(3, 4) == 7
    proxy_mgr.close_lib_proxy(proxy, run_sp=h.sp)
    # shutdown
    h.shutdown()


def libmgr_mgr_open_alib_libnix_test(buildlibnix):
    lib_file = buildlibnix.make_lib("testnix")
    lib_name = "testnix.library"
    open_alib(lib_file, lib_name)


def libmgr_mgr_open_alib_libsc_test(buildlibsc):
    lib_file = buildlibsc.make_lib("testsc")
    lib_name = "testsc.library"
    open_alib(lib_file, lib_name)


def libmgr_mgr_open_alib_libnix_ver_fail_test(buildlibnix):
    lib_file = buildlibnix.make_lib("testnix")
    lib_name = "testnix.library"
    open_alib(lib_file, lib_name, ok=False, version=99)


def libmgr_mgr_open_alib_libsc_ver_fail_test(buildlibsc):
    lib_file = buildlibsc.make_lib("testsc")
    lib_name = "testsc.library"
    open_alib(lib_file, lib_name, ok=False, version=99)


def libmgr_mgr_open_alib_libnix_mode_native_test(buildlibnix):
    lib_file = buildlibnix.make_lib("testnix")
    lib_name = "testnix.library"
    open_alib(lib_file, lib_name, mode=LibCfg.CREATE_MODE_AMIGA)


def libmgr_mgr_open_alib_libsc_mode_native_test(buildlibsc):
    lib_file = buildlibsc.make_lib("testsc")
    lib_name = "testsc.library"
    open_alib(lib_file, lib_name, mode=LibCfg.CREATE_MODE_AMIGA)


def libmgr_mgr_open_alib_libnix_mode_off_test(buildlibnix):
    lib_file = buildlibnix.make_lib("testnix")
    lib_name = "testnix.library"
    open_alib(lib_file, lib_name, ok=False, mode=LibCfg.CREATE_MODE_OFF)


def libmgr_mgr_open_alib_libsc_mode_off_test(buildlibsc):
    lib_file = buildlibsc.make_lib("testsc")
    lib_name = "testsc.library"
    open_alib(lib_file, lib_name, ok=False, mode=LibCfg.CREATE_MODE_OFF)
