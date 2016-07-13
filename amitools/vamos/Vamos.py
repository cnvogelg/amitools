from label.LabelManager import LabelManager
from label.LabelRange import LabelRange
from MemoryAlloc import MemoryAlloc
from MainMemory import MainMemory
from AccessMemory import AccessMemory
from AmigaLibrary import AmigaLibrary
from LibManager import LibManager
from SegmentLoader import SegmentLoader
from path.PathManager import PathManager
from ErrorTracker import ErrorTracker
from Trampoline import Trampoline
from HardwareAccess import HardwareAccess
from amitools.vamos.AccessStruct import AccessStruct
from amitools.vamos.lib.dos.DosStruct import CLIDef

# lib
from lib.ExecLibrary import ExecLibrary
from lib.DosLibrary import DosLibrary
from lib.UtilityLibrary import UtilityLibrary
from lib.IntuitionLibrary import IntuitionLibrary
from lib.MathFFPLibrary import MathFFPLibrary
from lib.MathIEEEDoubBasLibrary import MathIEEEDoubBasLibrary

from Log import *
from CPU import *
from Exceptions import *

class Vamos:

  def __init__(self, raw_mem, cpu, traps, cfg):
    self.raw_mem = raw_mem
    self.ram_size = raw_mem.get_ram_size() * 1024 # in bytes
    self.cpu = cpu
    self.cpu_type = cfg.cpu
    self.traps = traps
    self.cfg = cfg

    # too much RAM requested?
    # our "custom chips" start at $BFxxxx so we allow RAM only to be below
    if self.ram_size >= 0xbf0000 and self.cfg.hw_access != "disable":
      raise VamosConfigError("Too much RAM configured! Only up to $BF0000 allowed.")

    # setup custom chips
    if self.cfg.hw_access != "disable":
      self.hw_access = HardwareAccess(raw_mem)
      self._setup_hw_access()

    # path manager
    self.path_mgr = PathManager( cfg )

    # create a label manager and error tracker
    self.label_mgr = LabelManager()
    self.error_tracker = ErrorTracker(cpu, self.label_mgr)
    self.label_mgr.error_tracker = self.error_tracker

    # set a label for first two dwords
    label = LabelRange("zero_page",0,8)
    self.label_mgr.add_label(label)

    # create memory access
    self.mem = MainMemory(raw_mem, self.error_tracker)
    self.mem.ctx = self
    self._setup_memory(raw_mem)

    # create memory allocator
    self.mem_begin = 0x1000
    self.alloc = MemoryAlloc(self.mem, 0, self.ram_size, self.mem_begin, self.label_mgr)

    # create segment loader
    self.seg_loader = SegmentLoader( self.mem, self.alloc, self.label_mgr, self.path_mgr )

    # lib manager
    self.lib_mgr = LibManager( self.label_mgr, cfg)

    # no current process right now
    self.process = None
    self.proc_list = []

  def init(self):
    self.register_base_libs(self.cfg)
    self.create_old_dos_guard()
    self.open_base_libs()
    return True

  def cleanup(self):
    self.close_base_libs()
    self.alloc.dump_orphans()

  # ----- system setup -----

  def _setup_hw_access(self):
    # direct hw access
    cfg = self.cfg
    if cfg.hw_access == "emu":
      self.hw_access.set_mode(HardwareAccess.MODE_EMU)
    elif cfg.hw_access == "ignore":
      self.hw_access.set_mode(HardwareAccess.MODE_IGNORE)
    elif cfg.hw_access == "abort":
      self.hw_access.set_mode(HardwareAccess.MODE_ABORT)
    elif cfg.hw_access == "disable":
      pass
    else:
      raise VamosConfigError("Invalid HW Access mode: %s" % cfg.hw_access)

  def _setup_memory(self, mem):
    cfg = self.cfg
    # enable mem trace?
    if cfg.memory_trace:
      mem.set_trace_mode(1)
      mem.set_trace_func(self.label_mgr.trace_mem)
      if not log_mem.isEnabledFor(logging.DEBUG):
        log_mem.setLevel(logging.DEBUG)
    # enable internal memory trace?
    if cfg.internal_memory_trace:
      AccessMemory.label_mgr = self.label_mgr
      if not log_mem_int.isEnabledFor(logging.INFO):
        log_mem_int.setLevel(logging.INFO)
    # set invalid access handler for memory
    mem.set_invalid_func(self.error_tracker.report_invalid_memory)

  # ----- process handling -----

  def _set_this_task(self, proc):
    """tell exec about this process and all others referencing process from here"""
    self.process = proc
    self.exec_lib.set_this_task(proc)

  def get_current_process(self):
    return self.process

  def set_main_process(self, proc):
    log_proc.info("set main process: %s", proc)
    self.proc_list.append(proc)
    self._set_this_task(proc)

  def start_sub_process(self, proc):
    log_proc.info("start sub process: %s", proc)
    self.proc_list.append(proc)
    self._set_this_task(proc)

    # setup trampoline to enter sub process
    tr = Trampoline(self, "SubProcJump")
    # reserve a long for old stack
    old_stack_off = tr.dc_l(0)
    # code starts
    tr.save_all_but_d0()
    # new proc registers: d0=arg_len a0=arg_cptr
    tr.set_dx_l(0, proc.arg_len)
    tr.set_ax_l(0, proc.arg_base)
    # d2=stack_size.  this value is also in 4(sp) (see Process.init_stack), but
    # various C programs rely on it being present (1.3-3.1 at least have it).
    tr.set_dx_l(2, proc.stack_size)
    # to track old dos values
    tr.set_ax_l(2, self.dos_guard_base)
    tr.set_ax_l(5, self.dos_guard_base)
    tr.set_ax_l(6, self.dos_guard_base)
    # save old stack and set new stack
    tr.write_ax_l(7, old_stack_off, True) # write to data offset (dc.l above)
    new_stack = proc.stack_initial
    tr.set_ax_l(7, new_stack)
    # call code! (jmp - return value is on stack)
    tr.jmp(proc.prog_start)
    # restore stack (set a label to return from new stack - see below)
    return_off = tr.get_code_offset()
    tr.read_ax_l(7, old_stack_off, True) # read from data offset (dc.l above)
    # restore regs
    tr.restore_all_but_d0()
    # trap to clean up sub process resources
    def trap_stop_sub_process():
      self.stop_sub_process()
    tr.final_rts(trap_stop_sub_process)
    # realize trampoline in memory (data+code)
    tr.done()
    # get label addr -> set as return value of new stack
    return_addr = tr.get_code_addr(return_off)
    log_proc.debug("new_stack=%06x return_addr=%06x", new_stack, return_addr)
    # place return address for new process
    self.mem.access.w32(new_stack, return_addr)

  def stop_sub_process(self):
    # get return value
    ret_code = self.cpu.r_reg(REG_D0)
    # pop process
    proc = self.proc_list.pop()
    log_proc.info("stop sub process: %s ret_code=%d", proc, ret_code)
    proc.free()

  # ----- overload a process for RunCommand -----

  def run_command(self,start_pc,argsptr,arglen,stacksize):
    newstack     = self.alloc.alloc_memory("shell command stack",stacksize)
    newstackbase = newstack.addr
    newstacktop  = newstackbase + stacksize
    oldstackbase = self.process.this_task.access.r_s("pr_Task.tc_SPLower");
    oldstacktop  = self.process.this_task.access.r_s("pr_Task.tc_SPUpper");
    old_stackptr = self.cpu.r_reg(REG_A7) # addr of sys call return
    # put stack size on top of stack
    self.mem.access.w32(newstacktop - 4,stacksize)
    # activate new stack
    new_stackptr = newstacktop - 8
    self.process.this_task.access.w_s("pr_Task.tc_SPLower",newstackbase)
    self.process.this_task.access.w_s("pr_Task.tc_SPUpper",newstacktop)
    # NOTE: the Manx fexec and BPCL mess is not (yet) setup here.
    # setup trampoline to enter sub process
    tr = Trampoline(self, "RunCommand")
    # reserve a long for old stack
    old_stack_off = tr.dc_l(0)
    # code starts
    tr.save_all_but_d0()
    # new proc registers: d0=arg_len a0=arg_cptr
    tr.set_dx_l(0, arglen)
    tr.set_ax_l(0, argsptr)
    # d2=stack_size.  this value is also in 4(sp) (see Process.init_stack), but
    # various C programs rely on it being present (1.3-3.1 at least have it).
    tr.set_dx_l(2, stacksize)
    # to track old dos values
    tr.set_ax_l(2, self.dos_guard_base)
    tr.set_ax_l(5, self.dos_guard_base)
    tr.set_ax_l(6, self.dos_guard_base)
    # save old stack and set new stack
    tr.write_ax_l(7, old_stack_off, True) # write to data offset (dc.l above)
    tr.set_ax_l(7, new_stackptr)
    # call code! (jmp - return value is on stack)
    tr.jmp(start_pc)
    # restore stack (set a label to return from new stack - see below)
    return_off = tr.get_code_offset()
    tr.read_ax_l(7, old_stack_off, True) # read from data offset (dc.l above)
    # restore regs
    tr.restore_all_but_d0()
    # keep the old input file handle
    input_fh = self.process.get_input()
    # trap to clean up sub process resources
    def trap_stop_run_command():
      ret_code = self.cpu.r_reg(REG_D0)
      log_proc.info("return from RunCommand: ret_code=%d", ret_code)
      self.cpu.w_reg(REG_A7,old_stackptr)
      self.process.this_task.access.w_s("pr_Task.tc_SPLower",oldstackbase)
      self.process.this_task.access.w_s("pr_Task.tc_SPUpper",oldstacktop)
      self.alloc.free_memory(newstack)
      input_fh.setbuf("")
      # The return code remains in d0 as is
    tr.final_rts(trap_stop_run_command)
    # realize trampoline in memory (data+code)
    tr.done()
    # get label addr -> set as return value of new stack
    return_addr = tr.get_code_addr(return_off)
    log_proc.debug("new_stack=%06x return_addr=%06x", new_stackptr, return_addr)
    # place return address for new process
    self.mem.access.w32(new_stackptr, return_addr)

  def run_shell(self,start_pc,packet,stacksize,trap_stop_handler):
    newstack     = self.alloc.alloc_memory("shell command stack",stacksize)
    newstackbase = newstack.addr
    newstacktop  = newstackbase + stacksize
    oldstackbase = self.process.this_task.access.r_s("pr_Task.tc_SPLower");
    oldstacktop  = self.process.this_task.access.r_s("pr_Task.tc_SPUpper");
    old_stackptr = self.cpu.r_reg(REG_A7) # addr of sys call return
    # put stack size on top of stack
    self.mem.access.w32(newstacktop - 4,stacksize)
    # activate new stack
    new_stackptr = newstacktop - 8
    self.process.this_task.access.w_s("pr_Task.tc_SPLower",newstackbase)
    self.process.this_task.access.w_s("pr_Task.tc_SPUpper",newstacktop)
    # NOTE: the Manx fexec and BPCL mess is not (yet) setup here.
    # setup trampoline to enter sub process
    tr = Trampoline(self, "RunCommand")
    # reserve a long for old stack
    old_stack_off = tr.dc_l(0)
    # code starts
    tr.save_all_but_d0()
    # new proc registers: d1=packet
    tr.set_dx_l(1, packet >> 2)
    # d2=stack_size.  this value is also in 4(sp) (see Process.init_stack), but
    # various C programs rely on it being present (1.3-3.1 at least have it).
    tr.set_dx_l(2, stacksize)
    # to track old dos values
    tr.set_ax_l(2, self.dos_guard_base)
    tr.set_ax_l(5, self.dos_guard_base)
    tr.set_ax_l(6, self.dos_guard_base)
    # save old stack and set new stack
    tr.write_ax_l(7, old_stack_off, True) # write to data offset (dc.l above)
    tr.set_ax_l(7, new_stackptr)
    # call code! (jmp - return value is on stack)
    tr.jmp(start_pc)
    # restore stack (set a label to return from new stack - see below)
    return_off = tr.get_code_offset()
    tr.read_ax_l(7, old_stack_off, True) # read from data offset (dc.l above)
    # restore regs
    tr.restore_all_but_d0()
    def trap_stop_function():
      ret_code = self.cpu.r_reg(REG_D0)
      log_proc.info("return from SystemTagList: ret_code=%d", ret_code)
      self.cpu.w_reg(REG_A7,old_stackptr)
      self.process.this_task.access.w_s("pr_Task.tc_SPLower",oldstackbase)
      self.process.this_task.access.w_s("pr_Task.tc_SPUpper",oldstacktop)
      self.alloc.free_memory(newstack)
      trap_stop_handler(ret_code)
    tr.final_rts(trap_stop_function)
    # realize trampoline in memory (data+code)
    tr.done()
    # get label addr -> set as return value of new stack
    return_addr = tr.get_code_addr(return_off)
    log_proc.debug("new_stack=%06x return_addr=%06x", new_stackptr, return_addr)
    # place return address for new process
    self.mem.access.w32(new_stackptr, return_addr)

  # ----- init environment -----

  def register_base_libs(self, cfg):
    # register libraries
    # exec
    exec_cfg = cfg.get_lib_config('exec.library')
    self.exec_lib_def = ExecLibrary(self.lib_mgr, self.alloc, exec_cfg)
    self.lib_mgr.register_vamos_lib(self.exec_lib_def)
    # dos
    dos_cfg = cfg.get_lib_config('dos.library')
    self.dos_lib_def = DosLibrary(self.mem, self.alloc, self.path_mgr, dos_cfg)
    self.lib_mgr.register_vamos_lib(self.dos_lib_def)
    # intuition
    int_cfg = cfg.get_lib_config('intuition.library')
    self.int_lib_def = IntuitionLibrary(int_cfg)
    self.lib_mgr.register_vamos_lib(self.int_lib_def)
    # utility
    utility_cfg = cfg.get_lib_config('utility.library')
    self.utility_lib_def = UtilityLibrary(utility_cfg)
    self.lib_mgr.register_vamos_lib(self.utility_lib_def)
    # mathffp
    mathffp_cfg = cfg.get_lib_config('mathffp.library')
    self.mathffp_lib_def = MathFFPLibrary(mathffp_cfg)
    self.lib_mgr.register_vamos_lib(self.mathffp_lib_def)
    # mathdoubbas
    mathdoubbas_cfg = cfg.get_lib_config('mathieeedoubbas.library')
    self.mathdoubbas_lib_def = MathIEEEDoubBasLibrary(mathdoubbas_cfg)
    self.lib_mgr.register_vamos_lib(self.mathdoubbas_lib_def)

  def open_base_libs(self):
    # open exec lib
    self.exec_lib = self.lib_mgr.open_lib(ExecLibrary.name, 0, self)
    log_mem_init.info(self.exec_lib)
    # open dos lib
    self.dos_lib = self.lib_mgr.open_lib(DosLibrary.name, 0, self)
    log_mem_init.info(self.dos_lib)

  def close_base_libs(self):
    # close dos
    self.lib_mgr.close_lib(self.dos_lib.addr_base, self)
    # close exec
    self.lib_mgr.close_lib(self.exec_lib.addr_base, self)

  def create_old_dos_guard(self):
    # create a guard memory for tracking invalid old dos access
    self.dos_guard_base = self.mem.reserve_special_range()
    self.dos_guard_size = 0x010000
    label = LabelRange("old_dos guard",self.dos_guard_base, self.dos_guard_size)
    self.label_mgr.add_label(label)
    log_mem_init.info(label)
