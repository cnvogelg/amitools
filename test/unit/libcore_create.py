import datetime
from amitools.vamos.libcore import LibCreator, LibInfo, LibCtx, LibProfiler, LibProfilerConfig
from amitools.vamos.machine import MockMachine
from amitools.vamos.label import LabelManager
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary


def setup():
  machine = MockMachine(fill=23)
  mem = machine.get_mem()
  traps = machine.get_traps()
  cpu = machine.get_cpu()
  alloc = MemoryAlloc(mem)
  ctx = LibCtx(machine)
  return mem, traps, alloc, ctx


def libcore_create_lib_default_test():
  mem, traps, alloc, ctx = setup()
  impl = VamosTestLibrary()
  # create info for lib
  date = datetime.date(2012, 11, 12)
  info = LibInfo('vamostest.library', 42, 3, date)
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


def libcore_create_lib_fake_test():
  mem, traps, alloc, ctx = setup()
  impl = None
  # create info for lib
  date = datetime.date(2012, 11, 12)
  info = LibInfo('vamostest.library', 42, 3, date)
  # create lib
  creator = LibCreator(alloc, traps)
  lib = creator.create_lib(info, ctx, impl)
  # free lib
  lib.free()
  assert alloc.is_all_free()


def libcore_create_lib_profile_test():
  mem, traps, alloc, ctx = setup()
  impl = VamosTestLibrary()
  # create info for lib
  date = datetime.date(2012, 11, 12)
  info = LibInfo('vamostest.library', 42, 3, date)
  # create lib
  pc = LibProfilerConfig(profiling=True, all_libs=True)
  profiler = LibProfiler(pc)
  creator = LibCreator(alloc, traps, profiler=profiler)
  lib = creator.create_lib(info, ctx, impl)
  prof = profiler.get_profile('vamostest.library')
  assert prof
  # free lib
  lib.free()
  assert alloc.is_all_free()
