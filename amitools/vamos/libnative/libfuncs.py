from amitools.vamos.atypes import Library, LibFlags, NodeType, ExecLibrary
from amitools.vamos.loader import SegList
from amitools.vamos.machine.regs import *


class LibFuncs(object):

  LVO_Open = 1
  LVO_Close = 2
  LVO_Expunge = 3

  def __init__(self, machine, alloc):
    self.machine = machine
    self.mem = machine.get_mem()
    self.alloc = alloc

  def add_library(self, lib_base, exec_lib=None):
    lib = Library(self.mem, lib_base)
    lib.node.type = NodeType.NT_LIBRARY
    self.sum_library(lib_base)
    if exec_lib is None:
      exec_addr = self.mem.r32(4)
      exec_lib = ExecLibrary(self.mem, exec_addr)
    exec_lib.lib_list.enqueue(lib.node)

  def sum_library(self, lib_base):
    lib = Library(self.mem, lib_base)
    lib.flags.clr_bits(LibFlags.LIBF_CHANGED | LibFlags.LIBF_SUMUSED)
    lib.update_sum()

  def rem_library(self, lib_base, run_sp=None):
    seglist = self._run_expunge(lib_base, run_sp)
    if seglist != 0:
      sl = SegList(self.alloc, seglist)
      sl.free()
    return seglist

  def open_library(self, lib_base, run_sp=None):
    return self._run_open(lib_base, run_sp)

  def close_library(self, lib_base, run_sp=None):
    seglist = self._run_close(lib_base, run_sp)
    if seglist != 0:
      sl = SegList(self.alloc, seglist)
      sl.free()
    return seglist

  def _run_open(self, lib_base, run_sp=None):
    """call lib open and returns lib_base"""
    return self._run_lvo(lib_base, self.LVO_Open, "LibOpen", run_sp)

  def _run_close(self, lib_base, run_sp=None):
    """call lib close and return seg_list or 0"""
    return self._run_lvo(lib_base, self.LVO_Close, "LibOpen", run_sp)

  def _run_expunge(self, lib_base, run_sp=None):
    """call lib expunge and return seg_list or 0"""
    return self._run_lvo(lib_base, self.LVO_Expunge, "LibExpunge", run_sp)

  def _run_lvo(self, lib_base, lvo, name, run_sp=None):
    # call expunge func on lib
    func_addr = lib_base - lvo * 6
    set_regs = {
        REG_D0: lib_base
    }
    get_regs = [REG_D0]
    # run machine and share current sp if none is given
    rs = self.machine.run(func_addr, sp=run_sp,
                          set_regs=set_regs, get_regs=get_regs,
                          name=name)
    return rs.regs[REG_D0]
