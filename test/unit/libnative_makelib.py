from amitools.vamos.libnative import MakeLib, InitStructBuilder
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.machine import Machine
from amitools.vamos.machine.opcodes import *
from amitools.vamos.libstructs import LibraryStruct
from amitools.vamos.libtypes import Library


def libnative_makelib_test():
    machine = Machine()
    mem = machine.get_mem()
    sp = machine.get_ram_begin() - 4
    alloc = MemoryAlloc.for_machine(machine)

    # build lib info in memory
    vectors = 0x100
    mem.w32(vectors, 0x400)
    mem.w32(vectors + 4, 0x600)
    mem.w32(vectors + 8, 0x800)
    mem.w32(vectors + 12, 0xFFFFFFFF)
    name_addr = 0x1F0
    mem.w_cstr(name_addr, "bla.library")

    init_tab = 0x200
    ib = InitStructBuilder(mem, init_tab)
    name_off = LibraryStruct.sdef.lib_Node.ln_Name.base_offset
    ib.init_long(name_off, name_addr)
    ib.end()

    init_func = 0x300
    mem.w16(init_func, op_rts)

    pos_size = LibraryStruct.get_size()

    # make library
    ml = MakeLib(machine, alloc)
    lib_base, mem_obj = ml.make_library(
        vectors, init_tab, init_func, pos_size, 0, run_sp=sp
    )
    assert lib_base != 0

    # check library
    lib = Library(mem, lib_base)
    assert lib.name.str == "bla.library"
    assert lib.pos_size.val == 36
    assert lib.neg_size.val == 20  # round_long(3*6)
    assert mem.r32(lib_base - 4) == 0x400
    assert mem.r32(lib_base - 10) == 0x600
    assert mem.r32(lib_base - 16) == 0x800

    # cleanup
    alloc.free_memory(mem_obj)
    assert alloc.is_all_free()
