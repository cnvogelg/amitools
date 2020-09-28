from amitools.vamos.loader import SegList
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc


def loader_seglist_alloc_test(buildlibnix, mem_alloc):
    mem, alloc = mem_alloc
    sizes = [23, 17, 32]
    alloc_sizes = [24, 20, 32]
    # alloc seg_list
    seg_list = SegList.alloc(alloc, sizes)
    # check segment allocation
    assert seg_list.get_all_sizes() == alloc_sizes
    assert seg_list.get_all_addrs() == [12, 44, 72]
    segs = seg_list.get_all_segments()
    assert len(segs) == 3
    assert segs[0].get_size() == alloc_sizes[0]
    assert segs[1].get_size() == alloc_sizes[1]
    assert segs[2].get_size() == alloc_sizes[2]
    # iterator
    i = 0
    for seg in seg_list:
        assert seg.get_size() == alloc_sizes[i]
        i += 1
    # free
    seg_list.free()
    assert alloc.is_all_free()
