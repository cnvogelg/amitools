import collections
from amitools.vamos.lib.ExecLibrary import ExecLibrary
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary
from amitools.vamos.lib.VamosTestDevice import VamosTestDevice
from amitools.vamos.libcore import VLibManager
from amitools.vamos.machine import Machine
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.lib.lexec.ExecLibCtx import ExecLibCtx
from amitools.vamos.loader import SegmentLoader


def setup(main_profiler=None, prof_names=None, prof_calls=False):
    machine = Machine()
    alloc = MemoryAlloc(machine.get_mem(), machine.get_ram_begin())
    mgr = VLibManager(
        machine,
        alloc,
        main_profiler=main_profiler,
        prof_names=prof_names,
        prof_calls=prof_calls,
    )
    # setup ctx map
    cpu = machine.get_cpu()
    mem = machine.get_mem()
    cpu_type = machine.get_cpu_type()
    segloader = SegmentLoader(alloc)
    exec_ctx = ExecLibCtx(machine, alloc, segloader, None, None)
    # add extra attr to ctx
    mgr.set_ctx_extra_attr("foo", "bar")
    mgr.add_ctx("exec.library", exec_ctx)
    mgr.add_impl_cls("exec.library", ExecLibrary)
    mgr.add_impl_cls("vamostest.library", VamosTestLibrary)
    mgr.add_impl_cls("vamostestdev.device", VamosTestDevice)
    return machine, alloc, mgr


def libcore_mgr_bootstrap_shutdown_test():
    machine, alloc, mgr = setup()
    # bootstrap exec
    exec_vlib = mgr.bootstrap_exec()
    exec_base = exec_vlib.get_addr()
    exec_lib = exec_vlib.get_library()
    # make sure exec is in place
    assert mgr.get_vlib_by_name("exec.library") == exec_vlib
    assert mgr.get_vlib_by_addr(exec_base) == exec_vlib
    assert exec_lib.open_cnt.val == 1
    assert machine.get_mem().r32(4) == exec_base
    # check extra ctx attr
    assert exec_vlib.ctx.foo == "bar"
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
    test_vlib = mgr.make_lib_name("vamostest.library")
    test_base = test_vlib.get_addr()
    assert test_vlib
    assert mgr.get_vlib_by_name("vamostest.library") == test_vlib
    assert mgr.get_vlib_by_addr(test_base) == test_vlib
    impl = test_vlib.get_impl()
    assert impl
    assert impl.get_cnt() == 0
    lib = test_vlib.get_library()
    assert lib.version.val == impl.get_version()
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()


def libcore_mgr_make_version_revision_test():
    machine, alloc, mgr = setup()
    exec_vlib = mgr.bootstrap_exec()
    # make vamos test lib
    test_vlib = mgr.make_lib_name("vamostest.library", version=11, revision=23)
    test_base = test_vlib.get_addr()
    assert test_vlib
    assert mgr.get_vlib_by_name("vamostest.library") == test_vlib
    assert mgr.get_vlib_by_addr(test_base) == test_vlib
    impl = test_vlib.get_impl()
    assert impl
    assert impl.get_cnt() == 0
    lib = test_vlib.get_library()
    assert lib.version.val == 11
    assert lib.revision.val == 23
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()


def libcore_mgr_make_profile_test():
    machine, alloc, mgr = setup(prof_names=["all"])
    profiler = mgr.get_profiler()
    assert profiler
    profiler.setup()
    exec_vlib = mgr.bootstrap_exec()
    # make vamos test lib
    test_vlib = mgr.make_lib_name("vamostest.library")
    test_base = test_vlib.get_addr()
    assert test_vlib
    assert mgr.get_vlib_by_name("vamostest.library") == test_vlib
    assert mgr.get_vlib_by_addr(test_base) == test_vlib
    impl = test_vlib.get_impl()
    assert impl
    assert impl.get_cnt() == 0
    prof = test_vlib.profile
    assert prof
    assert profiler.get_profile("vamostest.library") == prof
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()
    # profile survives
    assert profiler.get_profile("vamostest.library") == prof


def libcore_mgr_make_fake_with_fd_test():
    machine, alloc, mgr = setup()
    exec_vlib = mgr.bootstrap_exec()
    # make vamos test lib
    test_vlib = mgr.make_lib_name("testnix.library")
    assert test_vlib is None
    test_vlib = mgr.make_lib_name("testnix.library", fake=True)
    test_base = test_vlib.get_addr()
    assert test_vlib
    assert mgr.get_vlib_by_name("testnix.library") == test_vlib
    assert mgr.get_vlib_by_addr(test_base) == test_vlib
    impl = test_vlib.get_impl()
    assert impl is None
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()


def libcore_mgr_make_fake_without_fd_test():
    machine, alloc, mgr = setup()
    exec_vlib = mgr.bootstrap_exec()
    # make vamos test lib
    test_vlib = mgr.make_lib_name("foo.library")
    assert test_vlib is None
    test_vlib = mgr.make_lib_name("foo.library", fake=True)
    test_base = test_vlib.get_addr()
    assert test_vlib
    assert mgr.get_vlib_by_name("foo.library") == test_vlib
    assert mgr.get_vlib_by_addr(test_base) == test_vlib
    impl = test_vlib.get_impl()
    assert impl is None
    assert test_vlib.get_fd().get_neg_size() == 30
    assert test_vlib.get_library().neg_size.val == 32
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()


def libcore_mgr_make_fake_without_fd_cfg_test():
    machine, alloc, mgr = setup()
    exec_vlib = mgr.bootstrap_exec()
    # lib_cfg
    Cfg = collections.namedtuple("Cfg", ["num_fake_funcs"])
    lib_cfg = Cfg(10)
    # make vamos test lib
    test_vlib = mgr.make_lib_name("foo.library", lib_cfg=lib_cfg)
    assert test_vlib is None
    test_vlib = mgr.make_lib_name("foo.library", fake=True, lib_cfg=lib_cfg)
    test_base = test_vlib.get_addr()
    assert test_vlib
    assert mgr.get_vlib_by_name("foo.library") == test_vlib
    assert mgr.get_vlib_by_addr(test_base) == test_vlib
    impl = test_vlib.get_impl()
    assert impl is None
    assert test_vlib.get_fd().get_neg_size() == 66
    assert test_vlib.get_library().neg_size.val == 68
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()


def libcore_mgr_make_open_test():
    machine, alloc, mgr = setup()
    exec_vlib = mgr.bootstrap_exec()
    # make vamos test lib
    test_vlib = mgr.make_lib_name("vamostest.library")
    test_base = test_vlib.get_addr()
    impl = test_vlib.get_impl()
    lib = test_vlib.get_library()
    assert lib.version.val == impl.get_version()
    assert impl.get_cnt() == 0
    assert mgr.open_lib_name("vamostest.library") == test_vlib
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
    test_vlib = mgr.open_lib_name("vamostest.library")
    impl = test_vlib.get_impl()
    lib = test_vlib.get_library()
    assert lib.version.val == impl.get_version()
    assert impl.get_cnt() == 1
    assert mgr.close_lib(test_vlib)
    assert impl.get_cnt() is None
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()


def libcore_mgr_make_open_dev_test():
    machine, alloc, mgr = setup()
    exec_vlib = mgr.bootstrap_exec()
    # make vamos test lib
    test_vlib = mgr.make_lib_name("vamostestdev.device")
    test_base = test_vlib.get_addr()
    impl = test_vlib.get_impl()
    lib = test_vlib.get_library()
    assert test_vlib.is_device()
    assert lib.version.val == impl.get_version()
    assert impl.get_cnt() == 0
    assert mgr.open_lib_name("vamostestdev.device") == test_vlib
    assert impl.get_cnt() == 1
    assert not mgr.expunge_lib(test_vlib)
    assert mgr.close_lib(test_vlib)
    assert impl.get_cnt() is None
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()


def libcore_mgr_open_dev_test():
    machine, alloc, mgr = setup()
    exec_vlib = mgr.bootstrap_exec()
    # make vamos test lib
    test_vlib = mgr.open_lib_name("vamostestdev.device")
    impl = test_vlib.get_impl()
    lib = test_vlib.get_library()
    assert test_vlib.is_device()
    assert lib.version.val == impl.get_version()
    assert impl.get_cnt() == 1
    assert mgr.close_lib(test_vlib)
    assert impl.get_cnt() is None
    # shutdown
    left = mgr.shutdown()
    assert left == 0
    assert alloc.is_all_free()
