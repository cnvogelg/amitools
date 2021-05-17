from amitools.vamos.loader import SegmentLoader
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.machine import Machine
from amitools.vamos.machine.regs import *
from amitools.vamos.libtypes import Resident, ExecLibrary, Library
from amitools.vamos.libstructs import ResidentFlags, NodeType, AutoInitStruct
from amitools.vamos.libnative import InitRes


def load_lib(alloc, buildlibnix):
    lib_file = buildlibnix.make_lib("testnix")
    loader = SegmentLoader(alloc)
    info = loader.int_load_sys_seglist(lib_file)
    seg_list = info.seglist
    seg = seg_list.get_segment()
    addr = seg.get_addr()
    size = seg.get_size()
    end = seg.get_end()
    return seg_list, addr, size, end


def libnative_initres_init_test(buildlibnix):
    machine = Machine()
    mem = machine.get_mem()
    cpu = machine.get_cpu()
    traps = machine.get_traps()
    alloc = MemoryAlloc.for_machine(machine)
    init_addr = machine.get_ram_begin() - 4
    sp = init_addr - 4
    # load lib
    seglist, addr, size, end = load_lib(alloc, buildlibnix)
    # setup init func
    def init_func(op, pc):
        assert cpu.r_reg(REG_A0) == seglist.get_baddr()
        # return my lib_base
        cpu.w_reg(REG_D0, 0xCAFEBABE)

    trap_id = traps.setup(init_func, auto_rts=True)
    mem.w16(init_addr, trap_id | 0xA000)
    # build fake resident
    res = Resident.alloc(alloc, name="bla.library", id_string="blub")
    res.new_resident(
        flags=0, version=42, type=NodeType.NT_LIBRARY, pri=-7, init=init_addr
    )
    # init resident
    ir = InitRes(machine, alloc)
    lib_base, mem_obj = ir.init_resident(res.get_addr(), seglist.get_baddr(), run_sp=sp)
    assert lib_base == 0xCAFEBABE
    assert mem_obj is None
    seglist.free()
    res.free()
    traps.free(trap_id)
    assert alloc.is_all_free()


def libnative_initres_autoinit_test(buildlibnix):
    machine = Machine()
    mem = machine.get_mem()
    cpu = machine.get_cpu()
    traps = machine.get_traps()
    alloc = MemoryAlloc.for_machine(machine)
    init_addr = machine.get_ram_begin() - 4
    sp = init_addr - 4
    # load lib
    seglist, addr, size, end = load_lib(alloc, buildlibnix)
    # setup init func
    def init_func(op, pc):
        assert cpu.r_reg(REG_A0) == seglist.get_baddr()

    trap_id = traps.setup(init_func, auto_rts=True)
    mem.w16(init_addr, trap_id | 0xA000)
    # fake vectors
    vectors = 0x100
    mem.w32(vectors, 0x400)
    mem.w32(vectors + 4, 0x600)
    mem.w32(vectors + 8, 0x800)
    mem.w32(vectors + 12, 0xFFFFFFFF)
    # build fake resident
    res = Resident.alloc(alloc, name="bla.library", id_string="blub")
    res.new_resident(
        flags=ResidentFlags.RTF_AUTOINIT, version=42, type=NodeType.NT_LIBRARY, pri=-7
    )
    auto_init = AutoInitStruct.alloc(alloc, functions=vectors, init_func=init_addr)
    res.init.ref = auto_init
    # setup exec lib
    exec_lib = ExecLibrary.alloc(
        alloc, name="exec.library", id_string="bla", neg_size=36
    )
    exec_lib.new_lib()
    mem.w32(4, exec_lib.get_addr())
    # init resident
    ir = InitRes(machine, alloc)
    lib_base, mem_obj = ir.init_resident(
        res.get_addr(), seglist.get_baddr(), run_sp=sp, exec_lib=exec_lib
    )
    assert lib_base
    assert mem_obj
    # check lib
    lib = Library(mem, lib_base)
    assert lib.name.str == "bla.library"
    assert lib.id_string.str == "blub"
    assert lib.neg_size.val == 20  # fits the 3*6 vectors
    # clean up
    seglist.free()
    res.free()
    auto_init.free()
    alloc.free_memory(mem_obj)
    exec_lib.free()
    traps.free(trap_id)
    assert alloc.is_all_free()
