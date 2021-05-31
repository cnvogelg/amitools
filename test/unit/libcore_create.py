import datetime
import collections
from amitools.vamos.libcore import LibCreator, LibInfo, LibCtx, LibProfiler
from amitools.vamos.machine import MockMachine
from amitools.vamos.label import LabelManager
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary


def setup():
    machine = MockMachine(fill=23)
    mem = machine.get_mem()
    traps = machine.get_traps()
    cpu = machine.get_cpu()
    alloc = MemoryAlloc.for_machine(machine)
    ctx = LibCtx(machine)
    return mem, traps, alloc, ctx


def libcore_create_lib_default_test():
    mem, traps, alloc, ctx = setup()
    impl = VamosTestLibrary()
    # create info for lib
    date = datetime.date(2012, 11, 12)
    info = LibInfo("vamostest.library", 42, 3, date)
    # create lib
    creator = LibCreator(alloc, traps)
    vlib = creator.create_lib(info, ctx, impl)
    assert impl.get_cnt() == 0
    # open
    vlib.open()
    assert impl.get_cnt() == 1
    # close
    vlib.close()
    assert impl.get_cnt() == 0
    # free lib
    vlib.free()
    assert impl.get_cnt() is None
    assert alloc.is_all_free()


def libcore_create_lib_fake_with_fd_test():
    mem, traps, alloc, ctx = setup()
    impl = None
    # create info for lib
    date = datetime.date(2012, 11, 12)
    info = LibInfo("vamostest.library", 42, 3, date)
    # create lib
    creator = LibCreator(alloc, traps)
    lib = creator.create_lib(info, ctx, impl)
    # free lib
    lib.free()
    assert alloc.is_all_free()


def libcore_create_lib_fake_without_fd_test():
    mem, traps, alloc, ctx = setup()
    impl = None
    # create info for lib
    date = datetime.date(2012, 11, 12)
    info = LibInfo("foo.library", 42, 3, date)
    # create lib
    creator = LibCreator(alloc, traps)
    lib = creator.create_lib(info, ctx, impl)
    assert lib.get_fd().get_neg_size() == 30
    assert lib.get_library().neg_size.val == 32
    # free lib
    lib.free()
    assert alloc.is_all_free()


def libcore_create_lib_fake_without_fd_cfg_test():
    mem, traps, alloc, ctx = setup()
    impl = None
    # create info for lib
    date = datetime.date(2012, 11, 12)
    info = LibInfo("foo.library", 42, 3, date)
    # lib_cfg
    Cfg = collections.namedtuple("Cfg", ["num_fake_funcs"])
    lib_cfg = Cfg(10)
    # create lib
    creator = LibCreator(alloc, traps)
    lib = creator.create_lib(info, ctx, impl, lib_cfg)
    assert lib.get_fd().get_neg_size() == 66
    assert lib.get_library().neg_size.val == 68
    # free lib
    lib.free()
    assert alloc.is_all_free()


def libcore_create_lib_label_test():
    mem, traps, alloc, ctx = setup()
    impl = None
    # create info for lib
    date = datetime.date(2012, 11, 12)
    info = LibInfo("vamostest.library", 42, 3, date)
    # create lib
    creator = LibCreator(alloc, traps)
    lib = creator.create_lib(info, ctx, impl)
    # check label
    assert alloc.get_label_mgr()
    label = lib.get_library()._mem_obj.label
    assert label
    assert label.fd == lib.get_fd()
    # free lib
    lib.free()
    assert alloc.is_all_free()


def libcore_create_lib_profile_test():
    mem, traps, alloc, ctx = setup()
    impl = VamosTestLibrary()
    # create info for lib
    date = datetime.date(2012, 11, 12)
    info = LibInfo("vamostest.library", 42, 3, date)
    # create lib
    lib_profiler = LibProfiler(names=["all"])
    creator = LibCreator(alloc, traps, lib_profiler=lib_profiler)
    lib_profiler.setup()
    lib = creator.create_lib(info, ctx, impl)
    profiler = creator.get_profiler()
    prof = profiler.get_profile("vamostest.library")
    assert prof
    assert lib.profile
    # free lib
    lib.free()
    assert alloc.is_all_free()
