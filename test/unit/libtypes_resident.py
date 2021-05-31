from amitools.vamos.loader import SegmentLoader
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.libstructs import ResidentFlags, NodeType
from amitools.vamos.libtypes import Resident


def load_lib(mem, buildlibnix):
    lib_file = buildlibnix.make_lib("testnix")
    alloc = MemoryAlloc(mem)
    loader = SegmentLoader(alloc)
    info = loader.int_load_sys_seglist(lib_file)
    seg_list = info.seglist
    seg = seg_list.get_segment()
    addr = seg.get_addr()
    size = seg.get_size()
    end = seg.get_end()
    return addr, size, end


def libtypes_resident_find_lib_test(buildlibnix):
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


def libtypes_resident_read_lib_test(buildlibnix):
    mem = MockMemory(fill=23)
    addr, size, end = load_lib(mem, buildlibnix)
    res = Resident.find(mem, addr, size)
    assert res.match_word.val == res.RTC_MATCHWORD
    assert res.match_tag.aptr == res.get_addr()
    assert res.end_skip.aptr >= res.get_addr() + res.get_size()
    assert res.flags.val == ResidentFlags.RTF_AUTOINIT
    assert res.version.val == 0
    assert res.type.val == NodeType.NT_LIBRARY
    assert res.pri.val == 0
    assert res.name.str == "testnix.library"
    assert res.id_string.str == "testnix.library 1.0 (07.07.2007)"
    ai = res.init.ref
    assert ai
    assert ai.addr == res.init.aptr
    assert ai.pos_size.val > 0
    assert ai.functions.aptr > 0
    assert ai.init_struct.aptr == 0
    assert ai.init_func.aptr > 0
    assert res.is_valid()


def libtypes_resident_alloc_test():
    mem = MockMemory(fill=23)
    alloc = MemoryAlloc(mem)
    # alloc
    res = Resident.alloc(alloc, name="bla.library", id_string="blub")
    # free
    res.free()
    assert alloc.is_all_free()


def libtypes_resident_setup_test():
    mem = MockMemory(fill=23)
    alloc = MemoryAlloc(mem)
    # alloc
    res2 = Resident.alloc(alloc, name="bla.library", id_string="blub")
    res2.new_resident(
        flags=ResidentFlags.RTF_AUTOINIT,
        version=42,
        type=NodeType.NT_DEVICE,
        pri=-7,
        init=0xDEADBEEF,
    )
    # find resource
    res = Resident.find(mem, 0, 1024)
    assert res.match_word.val == res.RTC_MATCHWORD
    assert res.match_tag.aptr == res.get_addr()
    assert res.end_skip.aptr >= res.get_addr() + res.get_size()
    assert res.flags.val == ResidentFlags.RTF_AUTOINIT
    assert res.version.val == 42
    assert res.type.val == NodeType.NT_DEVICE
    assert res.pri.val == -7
    assert res.name.str == "bla.library"
    assert res.id_string.str == "blub"
    assert res.init.aptr == 0xDEADBEEF
    # free
    res2.free()
    assert alloc.is_all_free()
