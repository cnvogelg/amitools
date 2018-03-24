from amitools.vamos.loader import SegmentLoader
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc


def loader_segload_test(binbuild):
  lib_file = binbuild.make_lib('simple')
  mem = MockMemory(fill=23)
  size = mem.get_ram_size() * 1024 - 0x100
  alloc = MemoryAlloc(mem, 0x100, size)
  loader = SegmentLoader(mem, alloc)
  seg_list = loader.load_seg(lib_file)
  assert seg_list is not None
