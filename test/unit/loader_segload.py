from amitools.vamos.loader import SegmentLoader
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc


def loader_segload_test(buildlibnix):
  lib_file = buildlibnix.make_lib('testnix')
  mem = MockMemory(fill=23)
  alloc = MemoryAlloc(mem)
  loader = SegmentLoader(mem, alloc)
  seg_list = loader.load_seglist(lib_file)
  assert seg_list is not None
  loader.unload_seglist(seg_list)
  assert alloc.is_all_free()
