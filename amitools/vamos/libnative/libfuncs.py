from amitools.vamos.libtypes import Library, ExecLibrary
from amitools.vamos.libstructs import LibFlags, NodeType
from amitools.vamos.loader import SegList
from amitools.vamos.machine.regs import *
from amitools.vamos.machine.opcodes import op_jmp


class LibFuncs(object):

    LVO_Open = 1
    LVO_Close = 2
    LVO_Expunge = 3

    def __init__(self, machine, alloc):
        self.machine = machine
        self.mem = machine.get_mem()
        self.alloc = alloc

    def find_library(self, lib_name, exec_lib=None):
        """find lib by name and return base addr or 0"""
        if exec_lib is None:
            exec_addr = self.mem.r32(4)
            exec_lib = ExecLibrary(self.mem, exec_addr)
        node = exec_lib.lib_list.find_name(lib_name)
        if node:
            return node.get_addr()
        else:
            return 0

    def add_library(self, lib_base, exec_lib=None):
        lib = Library(self.mem, lib_base)
        lib.node.type.val = NodeType.NT_LIBRARY
        self.sum_library(lib_base)
        if exec_lib is None:
            exec_addr = self.mem.r32(4)
            exec_lib = ExecLibrary(self.mem, exec_addr)
        exec_lib.lib_list.enqueue(lib.node)

    def sum_library(self, lib_base):
        lib = Library(self.mem, lib_base)
        lib.flags.clr_bits(LibFlags.LIBF_CHANGED | LibFlags.LIBF_SUMUSED)
        return lib.update_sum()

    def rem_library(self, lib_base, seg_loader, run_sp=None):
        seglist = self._run_expunge(lib_base, run_sp)
        if seglist != 0:
            seg_loader.unload_seglist(seglist)
        return seglist

    def open_library(self, lib_base, run_sp=None):
        return self._run_open(lib_base, run_sp)

    def close_library(self, lib_base, seg_loader, run_sp=None):
        seglist = self._run_close(lib_base, run_sp)
        if seglist != 0:
            seg_loader.unload_seglist(seglist)
        return seglist

    def set_function(self, lib_base, lvo, new_func_addr):
        """return old func addr or None if patch failed"""
        lib = Library(self.mem, lib_base)
        neg_size = lib.neg_size.val
        if lvo < 0:
            lvo = -lvo
        # check lvo range
        if lvo >= neg_size:
            return None
        # check that jmp is at lvo
        addr = lib_base - lvo
        jmp = self.mem.r16(addr)
        if jmp != op_jmp:
            return None
        # set new function
        old_func = self.mem.r32(addr + 2)
        self.mem.w32(addr + 2, new_func_addr)
        # sum lib
        self.sum_library(lib_base)
        return old_func

    def _run_open(self, lib_base, run_sp=None):
        """call lib open and returns lib_base"""
        return self._run_lvo(lib_base, self.LVO_Open, "LibOpen", run_sp)

    def _run_close(self, lib_base, run_sp=None):
        """call lib close and return seg_list or 0"""
        return self._run_lvo(lib_base, self.LVO_Close, "LibClose", run_sp)

    def _run_expunge(self, lib_base, run_sp=None):
        """call lib expunge and return seg_list or 0"""
        return self._run_lvo(lib_base, self.LVO_Expunge, "LibExpunge", run_sp)

    def _run_lvo(self, lib_base, lvo, name, run_sp=None):
        # call expunge func on lib
        func_addr = lib_base - lvo * 6
        set_regs = {REG_A6: lib_base}
        get_regs = [REG_D0]
        # run machine and share current sp if none is given
        rs = self.machine.run(
            func_addr, sp=run_sp, set_regs=set_regs, get_regs=get_regs, name=name
        )
        return rs.regs[REG_D0]
