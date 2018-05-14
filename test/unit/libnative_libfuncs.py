from amitools.vamos.machine import Machine
from amitools.vamos.machine.regs import *
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.libnative import LibFuncs
from amitools.vamos.atypes import ExecLibrary, Library, LibFlags
from amitools.vamos.loader import SegList, SegmentLoader


def libnative_libfuncs_add_library_test():
  machine = Machine()
  mem = machine.get_mem()
  alloc = MemoryAlloc.for_machine(machine)
  # setup exec lib
  exec_lib = ExecLibrary.alloc(alloc, "exec.library", "bla", 36)
  exec_lib.setup()
  mem.w32(4, exec_lib.get_addr())
  # new lib
  lib = Library.alloc(alloc, "my.library", "bla", 36)
  lib.setup()
  mem.w32(lib.get_addr()-36, 0xdeadbeef)
  # check lib sum
  assert lib.sum == 0
  # add lib
  lf = LibFuncs(machine, alloc)
  lf.add_library(lib.get_addr())
  # check that lib was added
  assert len(exec_lib.lib_list) == 1
  assert [a for a in exec_lib.lib_list] == [lib]
  assert lib.sum == 0xdeadbeef
  assert lf.find_library("my.library") == lib.get_addr()
  # cleanup
  lib.free()
  exec_lib.free()
  assert alloc.is_all_free()


def libnative_libfuncs_sum_library_test():
  machine = Machine()
  mem = machine.get_mem()
  alloc = MemoryAlloc.for_machine(machine)
  # new lib
  lib = Library.alloc(alloc, "my.library", "bla", 36)
  lib.setup()
  mem.w32(lib.get_addr() - 36, 0xdeadbeef)
  # sum lib
  lf = LibFuncs(machine, alloc)
  lf.sum_library(lib.get_addr())
  assert lib.sum == 0xdeadbeef
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
  lib = Library.alloc(alloc, "my.library", "bla", 36)
  lib.setup()
  # setup seglist
  seglist = SegList.alloc(alloc, [64])
  segloader.register_seglist(seglist.get_baddr())
  # setup expunge func

  def expunge_func(op, pc):
    # return my seglist
    cpu.w_reg(REG_D0, seglist.get_baddr())
  trap_id = traps.setup(expunge_func, auto_rts=True)
  exp_addr = lib.get_addr() - 18
  mem.w16(exp_addr, trap_id | 0xa000)
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
  lib = Library.alloc(alloc, "my.library", "bla", 36)
  lib.setup()
  # setup seglist
  seglist = SegList.alloc(alloc, [64])
  segloader.register_seglist(seglist.get_baddr())
  # setup expunge func

  def close_func(op, pc):
    # return my seglist
    cpu.w_reg(REG_D0, seglist.get_baddr())
  trap_id = traps.setup(close_func, auto_rts=True)
  exp_addr = lib.get_addr() - 12
  mem.w16(exp_addr, trap_id | 0xa000)
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
  lib = Library.alloc(alloc, "my.library", "bla", 36)
  lib.setup()
  # setup open func

  def open_func(op, pc):
    # return my seglist
    cpu.w_reg(REG_D0, 0xcafebabe)
  trap_id = traps.setup(open_func, auto_rts=True)
  exp_addr = lib.get_addr() - 6
  mem.w16(exp_addr, trap_id | 0xa000)
  # add lib
  lf = LibFuncs(machine, alloc)
  lib_base = lf.open_library(lib.get_addr(), run_sp=sp)
  assert lib_base == 0xcafebabe
  # cleanup
  lib.free()
  assert alloc.is_all_free()
