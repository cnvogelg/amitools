from .label import LabelManager, LabelRange
from .mem import MemoryAlloc
from .astructs import AccessStruct
from LibManager import LibManager
from .libcore import LibRegistry, LibCtxMap, LibCtx
from .loader import SegmentLoader
from path.PathManager import PathManager
from Trampoline import Trampoline
from HardwareAccess import HardwareAccess
from amitools.vamos.lib.lexec.ExecLibCtx import ExecLibCtx
from amitools.vamos.lib.dos.DosLibCtx import DosLibCtx
from amitools.vamos.lib.dos.Process import Process
from amitools.vamos.trace import TraceManager, TraceMemory

from Log import *
from .machine.regs import *
from .machine import CPUState
from Exceptions import *

class Vamos:

  def __init__(self, machine, cfg):
    self.machine = machine
    self.mem = machine.get_mem()
    self.raw_mem = self.mem
    self.ram_size = self.mem.get_ram_size_bytes()
    self.cpu = machine.get_cpu()
    self.cpu_type = machine.get_cpu_type()
    self.traps = machine.get_traps()
    self.cfg = cfg

    # too much RAM requested?
    # our "custom chips" start at $BFxxxx so we allow RAM only to be below
    if self.ram_size >= 0xbf0000 and self.cfg.hw_access != "disable":
      raise VamosConfigError("Too much RAM configured! Only up to $BF0000 allowed.")

    # setup custom chips
    if self.cfg.hw_access != "disable":
      self.hw_access = HardwareAccess(self.mem)
      self._setup_hw_access()

    # path manager
    self.path_mgr = PathManager(cfg)

    # create a label manager and error tracker
    self.label_mgr = machine.get_label_mgr()

    # set a label for first region
    if self.label_mgr:
      label = LabelRange("vbr",0,0x400)
      self.label_mgr.add_label(label)
      # shutdown range
      label = LabelRange("machine",0x400,0x800)
      self.label_mgr.add_label(label)

    # create memory access
    self.trace_mgr = TraceManager(self.cpu, self.label_mgr)
    if cfg.internal_memory_trace:
      self.mem = TraceMemory(self.mem, self.trace_mgr)
      if not log_mem_int.isEnabledFor(logging.INFO):
        log_mem_int.setLevel(logging.INFO)
    # enable mem trace?
    if cfg.memory_trace:
      self.machine.set_cpu_mem_trace_hook(self.trace_mgr.trace_mem)
      if not log_mem.isEnabledFor(logging.INFO):
        log_mem.setLevel(logging.INFO)
    # instr trace
    if cfg.instr_trace:
      if not log_instr.isEnabledFor(logging.INFO):
        log_instr.setLevel(logging.INFO)
      cpu = self.cpu
      trace_mgr = self.trace_mgr
      state = CPUState()
      def instr_hook():
        # add register dump
        if cfg.reg_dump:
          state.get(cpu)
          res = state.dump()
          for r in res:
            log_instr.info(r)
        # disassemble line
        pc = cpu.r_reg(REG_PC)
        trace_mgr.trace_code_line(pc)
      self.machine.set_instr_hook(instr_hook)

    # create memory allocator
    self.mem_begin = 0x1000
    self.mem_size = self.ram_size - self.mem_begin
    self.alloc = MemoryAlloc(self.mem, self.mem_begin, self.mem_size, self.label_mgr)

    # create segment loader
    self.seg_loader = SegmentLoader(self.alloc, self.path_mgr)

    # setup lib context
    ctx_map = LibCtxMap()
    self.exec_ctx = ExecLibCtx(self.machine, self.alloc,
                               self.seg_loader, self.path_mgr)
    self.dos_ctx = DosLibCtx(self.machine, self.alloc,
                             self.seg_loader, self.path_mgr,
                             self.run_command, self.start_sub_process)
    ctx_map.set_default_ctx(LibCtx(self.cpu, self.mem))
    ctx_map.add_ctx('exec.library', self.exec_ctx)
    ctx_map.add_ctx('dos.library', self.dos_ctx)

    # lib manager
    self.lib_reg = LibRegistry()
    self.lib_mgr = LibManager(self.label_mgr, self.lib_reg, ctx_map, cfg)
    self.exec_ctx.set_lib_mgr(self.lib_mgr)
    # on shutdown trigger lib manager to shutdown libs
    def shutdown():
      self.lib_mgr.shutdown()
    self.machine.set_shutdown_hook(shutdown)

    # no current process right now
    self.process = None
    self.proc_list = []

  def init(self, binary, arg_str, stack_size, shell, cwd):
    self.create_old_dos_guard()
    self.open_base_libs()
    return self.setup_main_proc(binary, arg_str, stack_size, shell, cwd)

  def cleanup(self, ok):
    self.cleanup_main_proc()
    self.close_base_libs()
    if ok:
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

  # ----- process handling -----

  def _set_this_task(self, proc):
    """tell exec about this process and all others referencing process from here"""
    self.process = proc
    self.exec_ctx.set_process(proc)
    self.exec_lib.set_this_task(proc)
    self.dos_ctx.set_process(proc)

  def get_current_process(self):
    return self.process

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
    self.mem.w32(new_stack, return_addr)

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
    self.mem.w32(newstacktop - 4,stacksize)
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
    self.mem.w32(new_stackptr, return_addr)

  def run_shell(self,start_pc,packet,stacksize,trap_stop_handler):
    newstack     = self.alloc.alloc_memory("shell command stack",stacksize)
    newstackbase = newstack.addr
    newstacktop  = newstackbase + stacksize
    oldstackbase = self.process.this_task.access.r_s("pr_Task.tc_SPLower");
    oldstacktop  = self.process.this_task.access.r_s("pr_Task.tc_SPUpper");
    old_stackptr = self.cpu.r_reg(REG_A7) # addr of sys call return
    # put stack size on top of stack
    self.mem.w32(newstacktop - 4,stacksize)
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
    self.mem.w32(new_stackptr, return_addr)

  # ----- init environment -----

  def open_base_libs(self):
    log_main.info("open_base_libs")
    # open exec lib
    self.exec_addr = self.lib_mgr.open_lib('exec.library', 0)
    self.exec_lib = self.lib_mgr.get_lib_impl(self.exec_addr)
    # link exec to dos
    self.dos_ctx.set_exec_lib(self.exec_lib)
    # open dos lib
    self.dos_addr = self.lib_mgr.open_lib('dos.library', 0)
    self.dos_lib = self.lib_mgr.get_lib_impl(self.dos_addr)
    self.dos_ctx.set_dos_lib(self.dos_lib)
    # set exec base @4
    self.machine.set_zero_mem(0, self.exec_addr)

  def close_base_libs(self):
    log_main.info("close_base_libs")
    # close dos
    self.lib_mgr.close_lib(self.dos_addr)
    # close exec
    self.lib_mgr.close_lib(self.exec_addr)

  def create_old_dos_guard(self):
    # create a guard memory for tracking invalid old dos access
    self.dos_guard_base = self.raw_mem.reserve_special_range()
    self.dos_guard_size = 0x010000
    if self.label_mgr:
      label = LabelRange("old_dos guard",self.dos_guard_base, self.dos_guard_size)
      self.label_mgr.add_label(label)
      log_mem_init.info(label)

  # ----- main process -----

  def setup_main_proc(self, binary, arg_str, stack_size, shell, cwd):
    proc = Process(self.dos_ctx, binary, arg_str, stack_size=stack_size,
                   shell=shell, cwd=cwd)
    if not proc.ok:
      return False
    log_proc.info("set main process: %s", proc)
    self.proc_list.append(proc)
    self._set_this_task(proc)
    self.main_proc = proc
    return True

  def get_initial_sp(self):
    return self.main_proc.get_initial_sp()

  def get_initial_pc(self):
    return self.main_proc.get_initial_pc()

  def get_initial_regs(self):
    regs = self.main_proc.get_initial_regs()
    # to track old dos values
    regs[REG_A2] = self.dos_guard_base
    regs[REG_A5] = self.dos_guard_base
    regs[REG_A6] = self.dos_guard_base
    return regs

  def cleanup_main_proc(self):
    self.main_proc.free()
