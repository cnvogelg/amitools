import datetime
from amitools.vamos.libcore import LibAllocMem, LibInfo
from amitools.vamos.machine import MockMemory
from amitools.vamos.AccessMemory import AccessMemory
from amitools.vamos.label import LabelManager
from amitools.vamos.MemoryAlloc import MemoryAlloc


def libcore_alloc_base_test():
  raw_mem = MockMemory(fill=23)
  mem = AccessMemory(raw_mem)
  size = raw_mem.get_ram_size() * 1024 - 0x100
  alloc = MemoryAlloc(mem, 0x100, size)
  # create info for lib
  date = datetime.date(2012, 11, 12)
  info = LibInfo('my.library', 42, 3, date, 36, 6*12)
  # create allocator
  lib_alloc = LibAllocMem(info, alloc)
  # create lib
  lib_mem = lib_alloc.alloc_lib()
  assert lib_mem is not None
  # retrieve info from mem
  info2 = lib_mem.read_info()
  assert info == info2
  # free lib
  lib_alloc.free_lib()
  assert alloc.available() == alloc.total()
