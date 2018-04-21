from amitools.vamos.loader import SegmentLoader
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc


def loader_segload_test(buildlibnix, mem_alloc):
  mem, alloc = mem_alloc
  lib_file = buildlibnix.make_lib('testnix')
  loader = SegmentLoader(alloc)
  seg_list = loader.load_seglist(lib_file)
  assert seg_list
  seg_list.free()
  assert alloc.is_all_free()
