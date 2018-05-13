from amitools.vamos.loader import SegmentLoader
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.atypes import Resident, ResidentFlags, NodeType


def load_lib(mem, buildlibnix):
  lib_file = buildlibnix.make_lib('testnix')
  alloc = MemoryAlloc(mem)
  loader = SegmentLoader(alloc)
  info = loader.int_load_sys_seglist(lib_file)
  seg_list = info.seglist
  seg = seg_list.get_segment()
  addr = seg.get_addr()
  size = seg.get_size()
  end = seg.get_end()
  return addr, size, end


def atypes_resident_find_lib_test(buildlibnix):
  mem = MockMemory(fill=23)
  addr, size, end = load_lib(mem, buildlibnix)
  # search list
  res = Resident.find(mem, addr, size, only_first=False)
  assert len(res) == 1
  assert res[0].is_valid()
  res_obj = res[0]
  assert res_obj.get_addr() > addr
  assert res_obj.get_addr() < end
  # search first only
  res2 = Resident.find(mem, addr, size)
  assert res == [res2]
  assert res2.is_valid()


def atypes_resident_read_lib_test(buildlibnix):
  mem = MockMemory(fill=23)
  addr, size, end = load_lib(mem, buildlibnix)
  res = Resident.find(mem, addr, size)
  assert res.get_match_word() == res.RTC_MATCHWORD
  assert res.get_match_tag() == res.get_addr()
  assert res.get_end_skip() >= res.get_addr() + res.get_type_size()
  assert res.get_flags() == ResidentFlags.RTF_AUTOINIT
  assert res.get_version() == 0
  assert res.get_type() == NodeType.NT_LIBRARY
  assert res.get_pri() == 0
  assert res.get_name() == "testnix.library"
  assert res.get_id_string() == "testnix.library 1.0 (07.07.2007)"
  assert res.get_init() > 0
  ai = res.get_auto_init()
  assert ai.get_addr() == res.get_init()
  assert ai.get_pos_size() > 0
  assert ai.get_functions() > 0
  assert ai.get_init_struct() == 0
  assert ai.get_init_func() > 0
  assert res.is_valid()


def atypes_resident_alloc_test():
  mem = MockMemory(fill=23)
  alloc = MemoryAlloc(mem)
  # alloc
  res = Resident.alloc(alloc, "bla.library", "blub")
  # free
  res.free()
  assert alloc.is_all_free()


def atypes_resident_setup_test():
  mem = MockMemory(fill=23)
  alloc = MemoryAlloc(mem)
  # alloc
  res2 = Resident.alloc(alloc, "bla.library", "blub")
  res2.setup(flags=ResidentFlags.RTF_AUTOINIT, version=42,
             type=NodeType.NT_DEVICE, pri=-7, init=0xdeadbeef)
  # find resource
  res = Resident.find(mem, 0, 1024)
  assert res.get_match_word() == res.RTC_MATCHWORD
  assert res.get_match_tag() == res.get_addr()
  assert res.get_end_skip() >= res.get_addr() + res.get_type_size()
  assert res.get_flags() == ResidentFlags.RTF_AUTOINIT
  assert res.get_version() == 42
  assert res.get_type() == NodeType.NT_DEVICE
  assert res.get_pri() == -7
  assert res.get_name() == "bla.library"
  assert res.get_id_string() == "blub"
  assert res.get_init() == 0xdeadbeef
  # free
  res2.free()
  assert alloc.is_all_free()
