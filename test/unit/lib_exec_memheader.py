from amitools.vamos.lib.lexec.memheader import AllocatorMemHeader
from amitools.vamos.libstructs import ListStruct
from amitools.vamos.libtypes import List
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc


def exec_memheader_tracks_fragmentation_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem, addr=0x1000, alignment=8)
    storage = ListStruct.alloc(alloc)
    listing = List(mem, storage.addr)
    listing.new(10)
    view = AllocatorMemHeader(alloc, listing)

    def check():
        header = view.header
        assert listing.get_head().addr == header.addr
        assert header.mh_Attributes.val == 5
        assert header.mh_Lower.aptr == alloc.addr
        assert header.mh_Upper.aptr == alloc.addr + alloc.size
        expected = []
        chunk = alloc.free_first
        while chunk:
            expected.append((chunk.addr, chunk.size))
            chunk = chunk.next
        actual = []
        address = header.mh_First.aptr
        while address:
            actual.append((address, mem.r32(address + 4)))
            address = mem.r32(address)
        assert actual == expected
        assert (
            header.mh_Free.val == alloc.available() == sum(size for _, size in actual)
        )

    check()
    a = alloc.alloc_mem(1)
    b = alloc.alloc_mem(19)
    c = alloc.alloc_mem(7)
    check()
    alloc.free_mem(b, 19)
    check()
    assert mem.r_block(a, 8) == mem.r_block(c, 8) == bytes(8)
    alloc.free_mem(a, 1)
    alloc.free_mem(c, 7)
    check()
    view.free()
    assert listing.is_empty()
    storage.free()
    assert alloc.change_callback is None and alloc.is_all_free()
