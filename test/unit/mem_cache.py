from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryCache


def mem_cache_rwx_write_test():
    mem = MemoryCache(0x100, 0x210)
    # build cache contents
    mem.w8(0x100, 42)
    assert mem.r8(0x100) == 42
    mem.w16(0x200, 0xDEAD)
    assert mem.r16(0x200) == 0xDEAD
    mem.w32(0x300, 0xCAFEBABE)
    assert mem.r32(0x300) == 0xCAFEBABE
    mem.write(0, 0x101, 43)
    assert mem.read(0, 0x101) == 43
    mem.write(1, 0x202, 0x1234)
    assert mem.read(1, 0x202) == 0x1234
    mem.write(2, 0x304, 0x11223344)
    assert mem.read(2, 0x304) == 0x11223344
    # write to main mem
    main_mem = MockMemory()
    mem.write_cache(main_mem)
    # check main mem
    assert main_mem.r8(0x100) == 42
    assert main_mem.r16(0x200) == 0xDEAD
    assert main_mem.r32(0x300) == 0xCAFEBABE
    assert main_mem.read(0, 0x101) == 43
    assert main_mem.read(1, 0x202) == 0x1234
    assert main_mem.read(2, 0x304) == 0x11223344


def mem_cache_rwx_read_test():
    mem = MockMemory()
    # build main mem contents
    mem.w8(0x100, 42)
    assert mem.r8(0x100) == 42
    mem.w16(0x200, 0xDEAD)
    assert mem.r16(0x200) == 0xDEAD
    mem.w32(0x300, 0xCAFEBABE)
    assert mem.r32(0x300) == 0xCAFEBABE
    mem.write(0, 0x101, 43)
    assert mem.read(0, 0x101) == 43
    mem.write(1, 0x202, 0x1234)
    assert mem.read(1, 0x202) == 0x1234
    mem.write(2, 0x304, 0x11223344)
    assert mem.read(2, 0x304) == 0x11223344
    # write to cache
    cmem = MemoryCache(0x100, 0x210)
    cmem.read_cache(mem)
    # check cache mem
    assert cmem.r8(0x100) == 42
    assert cmem.r16(0x200) == 0xDEAD
    assert cmem.r32(0x300) == 0xCAFEBABE
    assert cmem.read(0, 0x101) == 43
    assert cmem.read(1, 0x202) == 0x1234
    assert cmem.read(2, 0x304) == 0x11223344


def mem_cache_rwxs_write_test():
    mem = MemoryCache(0x100, 0x210)
    # build cache contents
    mem.w8s(0x100, -42)
    assert mem.r8s(0x100) == -42
    mem.w16s(0x200, -0x1EAD)
    assert mem.r16s(0x200) == -0x1EAD
    mem.w32s(0x300, -0x2AFEBABE)
    assert mem.r32s(0x300) == -0x2AFEBABE
    mem.writes(0, 0x101, -43)
    assert mem.reads(0, 0x101) == -43
    mem.writes(1, 0x202, -0x1234)
    assert mem.reads(1, 0x202) == -0x1234
    mem.writes(2, 0x304, -0x11223344)
    assert mem.reads(2, 0x304) == -0x11223344
    # write to main mem
    main_mem = MockMemory()
    mem.write_cache(main_mem)
    # check main mem
    assert main_mem.r8s(0x100) == -42
    assert main_mem.r16s(0x200) == -0x1EAD
    assert main_mem.r32s(0x300) == -0x2AFEBABE
    assert main_mem.reads(0, 0x101) == -43
    assert main_mem.reads(1, 0x202) == -0x1234
    assert main_mem.reads(2, 0x304) == -0x11223344


def mem_cache_rwxs_read_test():
    mem = MockMemory()
    # build main mem contents
    mem.w8s(0x100, -42)
    assert mem.r8s(0x100) == -42
    mem.w16s(0x200, -0x1EAD)
    assert mem.r16s(0x200) == -0x1EAD
    mem.w32s(0x300, -0x2AFEBABE)
    assert mem.r32s(0x300) == -0x2AFEBABE
    mem.writes(0, 0x101, -43)
    assert mem.reads(0, 0x101) == -43
    mem.writes(1, 0x202, -0x1234)
    assert mem.reads(1, 0x202) == -0x1234
    mem.writes(2, 0x304, -0x11223344)
    assert mem.reads(2, 0x304) == -0x11223344
    # write to cache
    cmem = MemoryCache(0x100, 0x210)
    cmem.read_cache(mem)
    # check cache mem
    assert cmem.r8s(0x100) == -42
    assert cmem.r16s(0x200) == -0x1EAD
    assert cmem.r32s(0x300) == -0x2AFEBABE
    assert cmem.reads(0, 0x101) == -43
    assert cmem.reads(1, 0x202) == -0x1234
    assert cmem.reads(2, 0x304) == -0x11223344


def mem_cache_block_write_test():
    mem = MemoryCache(0x100, 0x220)
    data = b"hello, world!"
    mem.w_block(0x100, data)
    assert mem.r_block(0x100, len(data)) == data
    bdata = bytearray(data)
    mem.w_block(0x180, bdata)
    assert mem.r_block(0x180, len(bdata)) == bdata
    mem.clear_block(0x200, 100, 42)
    assert mem.r_block(0x200, 100) == bytes([42] * 100)
    mem.copy_block(0x200, 0x300, 20)
    assert mem.r_block(0x300, 21) == bytes([42] * 20) + b"\0"
    # write to main mem
    main_mem = MockMemory()
    mem.write_cache(main_mem)
    assert main_mem.r_block(0x100, len(data)) == data
    assert main_mem.r_block(0x180, len(bdata)) == bdata
    assert main_mem.r_block(0x200, 100) == bytes([42] * 100)
    assert main_mem.r_block(0x300, 21) == bytes([42] * 20) + b"\0"


def mem_cache_block_read_test():
    mem = MockMemory()
    data = b"hello, world!"
    mem.w_block(0x100, data)
    assert mem.r_block(0x100, len(data)) == data
    bdata = bytearray(data)
    mem.w_block(0x180, bdata)
    assert mem.r_block(0x180, len(bdata)) == bdata
    mem.clear_block(0x200, 100, 42)
    assert mem.r_block(0x200, 100) == bytes([42] * 100)
    mem.copy_block(0x200, 0x300, 20)
    assert mem.r_block(0x300, 21) == bytes([42] * 20) + b"\0"
    # write to main mem
    cmem = MemoryCache(0x100, 0x220)
    cmem.read_cache(mem)
    assert cmem.r_block(0x100, len(data)) == data
    assert cmem.r_block(0x180, len(bdata)) == bdata
    assert cmem.r_block(0x200, 100) == bytes([42] * 100)
    assert cmem.r_block(0x300, 21) == bytes([42] * 20) + b"\0"


def mem_cache_cstr_write_test():
    mem = MemoryCache(0x100, 0x100)
    data = "hello, world"
    mem.w_cstr(0x100, data)
    assert mem.r_cstr(0x100) == data
    empty = ""
    mem.w_cstr(0x120, empty)
    assert mem.r_cstr(0x120) == empty
    # to main
    main_mem = MockMemory()
    mem.write_cache(main_mem)
    assert main_mem.r_cstr(0x100) == data
    assert main_mem.r_cstr(0x120) == empty


def mem_cache_cstr_read_test():
    mem = MockMemory()
    data = "hello, world"
    mem.w_cstr(0x100, data)
    assert mem.r_cstr(0x100) == data
    empty = ""
    mem.w_cstr(0x120, empty)
    assert mem.r_cstr(0x120) == empty
    # to cache
    cmem = MemoryCache(0x100, 0x100)
    cmem.read_cache(mem)
    assert cmem.r_cstr(0x100) == data
    assert cmem.r_cstr(0x120) == empty


def mem_cache_bstr_write_test():
    mem = MemoryCache(0x100, 0x100)
    data = "hello, world"
    mem.w_bstr(0x100, data)
    assert mem.r_bstr(0x100) == data
    empty = ""
    mem.w_bstr(0x180, empty)
    assert mem.r_bstr(0x180) == empty
    # to main
    main_mem = MockMemory()
    mem.write_cache(main_mem)
    assert main_mem.r_bstr(0x100) == data
    assert main_mem.r_bstr(0x180) == empty


def mem_cache_bstr_read_test():
    mem = MockMemory()
    mem = MemoryCache(0x100, 0x100)
    data = "hello, world"
    mem.w_bstr(0x100, data)
    assert mem.r_bstr(0x100) == data
    empty = ""
    mem.w_bstr(0x180, empty)
    assert mem.r_bstr(0x180) == empty
    # to cache
    cmem = MemoryCache(0x100, 0x100)
    cmem.read_cache(mem)
    assert cmem.r_bstr(0x100) == data
    assert cmem.r_bstr(0x180) == empty
