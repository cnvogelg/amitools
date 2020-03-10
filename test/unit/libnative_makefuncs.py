from amitools.vamos.machine import MockMemory
from amitools.vamos.libnative import MakeFuncs
from amitools.vamos.machine.opcodes import op_jmp


def make_functions_offset_test():
    mem = MockMemory()
    # build an offset array
    ptr = 0
    offsets = [-10, 2, 16, 32, 68, 100]
    for off in offsets:
        mem.w16s(ptr, off)
        ptr += 2
    mem.w16s(ptr, -1)
    # build func table
    disp_base = 0x1000
    lib_base = 0x800
    mf = MakeFuncs(mem)
    size = mf.make_functions(lib_base, 0, disp_base)
    assert size == len(offsets) * 6
    # check jump table
    ptr = lib_base - 6
    for off in offsets:
        addr = disp_base + off
        assert mem.r16(ptr) == op_jmp
        assert mem.r32(ptr + 2) == addr
        ptr -= 6


def make_functions_ptr_test():
    mem = MockMemory()
    # build an offset array
    ptr = 0
    fptrs = [0x100, 0x202, 0x404, 0x808, 0x10000]
    for fptr in fptrs:
        mem.w32(ptr, fptr)
        ptr += 4
    mem.w32s(ptr, -1)
    # build func table
    lib_base = 0x800
    mf = MakeFuncs(mem)
    size = mf.make_functions(lib_base, 0)
    assert size == len(fptrs) * 6
    # check jump table
    ptr = lib_base - 6
    for fptr in fptrs:
        assert mem.r16(ptr) == op_jmp
        assert mem.r32(ptr + 2) == fptr
        ptr -= 6
