from amitools.vamos.machine import Machine
from amitools.vamos.machine.regs import *
from amitools.vamos.machine.opcodes import op_jmp
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.libnative import LibFuncs
from amitools.vamos.libtypes import ExecLibrary, Library
from amitools.vamos.libstructs import LibFlags
from amitools.vamos.loader import SegList, SegmentLoader


def libnative_libfuncs_add_library_test():
    machine = Machine()
    mem = machine.get_mem()
    alloc = MemoryAlloc.for_machine(machine)
    # setup exec lib
    exec_lib = ExecLibrary.alloc(
        alloc, name="exec.library", id_string="bla", neg_size=36
    )
    assert exec_lib.LibNode.neg_size.val == 36
    assert exec_lib.LibNode.pos_size.val == ExecLibrary.get_size()
    exec_lib.new_lib()
    mem.w32(4, exec_lib.get_addr())
    # new lib
    lib = Library.alloc(alloc, name="my.library", id_string="bla", neg_size=36)
    assert lib.neg_size.val == 36
    lib.new_lib()
    mem.w32(lib.get_addr() - 36, 0xDEADBEEF)
    # check initial lib sum
    assert lib.sum.val == 0
    assert lib.calc_sum() == 0xDEADBEEF
    # add lib
    lf = LibFuncs(machine, alloc)
    lf.add_library(lib.addr)
    # check that lib was added
    assert len(exec_lib.lib_list) == 1
    libs = [a for a in exec_lib.lib_list]
    assert list(map(lambda x: x.addr, libs)) == [lib.addr]
    # check that libsum was calced
    assert lib.sum.val == 0xDEADBEEF
    assert lf.find_library("my.library") == lib.addr
    # cleanup
    lib.free()
    exec_lib.free()
    assert alloc.is_all_free()


def libnative_libfuncs_sum_library_test():
    machine = Machine()
    mem = machine.get_mem()
    alloc = MemoryAlloc.for_machine(machine)
    # new lib
    lib = Library.alloc(alloc, name="my.library", id_string="bla", neg_size=36)
    lib.new_lib()
    mem.w32(lib.get_addr() - 36, 0xDEADBEEF)
    # sum lib
    lf = LibFuncs(machine, alloc)
    lf.sum_library(lib.get_addr())
    assert lib.sum.val == 0xDEADBEEF
    # cleanup
    lib.free()
    assert alloc.is_all_free()


def libnative_libfuncs_rem_library_test():
    machine = Machine()
    mem = machine.get_mem()
    cpu = machine.get_cpu()
    traps = machine.get_traps()
    sp = machine.get_ram_begin() - 4
    alloc = MemoryAlloc.for_machine(machine)
    segloader = SegmentLoader(alloc)
    # new lib
    lib = Library.alloc(alloc, name="my.library", id_string="bla", neg_size=36)
    lib.new_lib()
    # setup seglist
    seglist = SegList.alloc(alloc, [64])
    segloader.register_seglist(seglist.get_baddr())
    # setup expunge func

    def expunge_func(op, pc):
        # return my seglist
        cpu.w_reg(REG_D0, seglist.get_baddr())

    trap_id = traps.setup(expunge_func, auto_rts=True)
    exp_addr = lib.get_addr() - 18
    mem.w16(exp_addr, trap_id | 0xA000)
    # add lib
    lf = LibFuncs(machine, alloc)
    sl = lf.rem_library(lib.get_addr(), segloader, run_sp=sp)
    assert seglist.get_baddr() == sl
    # cleanup
    lib.free()
    assert alloc.is_all_free()
    assert segloader.shutdown() == 0


def libnative_libfuncs_close_library_test():
    machine = Machine()
    mem = machine.get_mem()
    cpu = machine.get_cpu()
    traps = machine.get_traps()
    sp = machine.get_ram_begin() - 4
    alloc = MemoryAlloc.for_machine(machine)
    segloader = SegmentLoader(alloc)
    # new lib
    lib = Library.alloc(alloc, name="my.library", id_string="bla", neg_size=36)
    lib.new_lib()
    # setup seglist
    seglist = SegList.alloc(alloc, [64])
    segloader.register_seglist(seglist.get_baddr())
    # setup expunge func

    def close_func(op, pc):
        # return my seglist
        cpu.w_reg(REG_D0, seglist.get_baddr())

    trap_id = traps.setup(close_func, auto_rts=True)
    exp_addr = lib.get_addr() - 12
    mem.w16(exp_addr, trap_id | 0xA000)
    # add lib
    lf = LibFuncs(machine, alloc)
    sl = lf.close_library(lib.get_addr(), segloader, run_sp=sp)
    assert seglist.get_baddr() == sl
    # cleanup
    lib.free()
    assert alloc.is_all_free()
    assert segloader.shutdown() == 0


def libnative_libfuncs_open_library_test():
    machine = Machine()
    mem = machine.get_mem()
    cpu = machine.get_cpu()
    traps = machine.get_traps()
    sp = machine.get_ram_begin() - 4
    alloc = MemoryAlloc.for_machine(machine)
    # new lib
    lib = Library.alloc(alloc, name="my.library", id_string="bla", neg_size=36)
    lib.new_lib()
    # setup open func

    def open_func(op, pc):
        # return my seglist
        cpu.w_reg(REG_D0, 0xCAFEBABE)

    trap_id = traps.setup(open_func, auto_rts=True)
    exp_addr = lib.get_addr() - 6
    mem.w16(exp_addr, trap_id | 0xA000)
    # add lib
    lf = LibFuncs(machine, alloc)
    lib_base = lf.open_library(lib.get_addr(), run_sp=sp)
    assert lib_base == 0xCAFEBABE
    # cleanup
    lib.free()
    assert alloc.is_all_free()


def libnative_libfuncs_set_function_test():
    machine = Machine()
    mem = machine.get_mem()
    cpu = machine.get_cpu()
    sp = machine.get_ram_begin() - 4
    alloc = MemoryAlloc.for_machine(machine)
    # new lib
    lib = Library.alloc(alloc, name="my.library", id_string="bla", neg_size=36)
    lib_addr = lib.get_addr()
    lib.new_lib()
    lib.fill_funcs(op_jmp, 0xCAFEBABE)
    assert lib.neg_size.val == 36
    # patch function
    lvo = -30
    addr = lib.get_addr() + lvo
    assert mem.r16(addr) == op_jmp
    assert mem.r32(addr + 2) == 0xCAFEBABE
    lf = LibFuncs(machine, alloc)
    old_addr = lf.set_function(lib_addr, lvo, 0xDEADBEEF)
    assert old_addr == 0xCAFEBABE
    assert mem.r16(addr) == op_jmp
    assert mem.r32(addr + 2) == 0xDEADBEEF
    assert lib.check_sum()
    # invalid function
    old_addr = lf.set_function(lib_addr, -36, 0)
    assert old_addr is None
    # cleanup
    lib.free()
    assert alloc.is_all_free()
