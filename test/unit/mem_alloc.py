from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc


def mem_alloc_base_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    assert alloc.is_all_free()
    addr = alloc.alloc_mem(1024)
    alloc.free_mem(addr, 1024)
    assert alloc.is_all_free()


def mem_alloc_nonbase4_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    assert alloc.is_all_free()
    addr = alloc.alloc_mem(1021)
    alloc.free_mem(addr, 1021)
    assert alloc.is_all_free()
