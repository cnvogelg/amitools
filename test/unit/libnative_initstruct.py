from amitools.vamos.machine import MockMemory
from amitools.vamos.libnative import InitStruct, InitStructBuilder


def init_struct_test():
    mem = MockMemory()
    # setup init table
    init_tab = 0x100
    mem_ptr = 0x200
    ib = InitStructBuilder(mem, init_tab)
    ib.init_byte(0, 21)
    ib.init_word(12, 0xDEAD)
    ib.init_long(34, 0xCAFEBABE)
    ib.init_struct(ib.SIZE_LONG, 40, [23, 42])
    ib.init_struct(ib.SIZE_WORD, 64, [11, 7])
    ib.init_struct(ib.SIZE_BYTE, 80, [1, 2, 3])
    ib.end()
    # build struct
    i = InitStruct(mem)
    i.init_struct(init_tab, mem_ptr, 32)
    # check struct
    assert mem.r8(mem_ptr + 0) == 21
    assert mem.r16(mem_ptr + 12) == 0xDEAD
    assert mem.r32(mem_ptr + 34) == 0xCAFEBABE
    assert mem.r32(mem_ptr + 40) == 23
    assert mem.r32(mem_ptr + 44) == 42
    assert mem.r16(mem_ptr + 64) == 11
    assert mem.r16(mem_ptr + 66) == 7
    assert mem.r8(mem_ptr + 80) == 1
    assert mem.r8(mem_ptr + 81) == 2
    assert mem.r8(mem_ptr + 82) == 3
