from .label import LabelManager, LabelRange
from .astructs import AccessStruct
from .libcore import LibProfilerConfig
from .loader import SegmentLoader
from .libmgr import LibManager, LibMgrCfg
from Trampoline import Trampoline
from amitools.vamos.lib.lexec.ExecLibCtx import ExecLibCtx
from amitools.vamos.lib.dos.DosLibCtx import DosLibCtx
from amitools.vamos.lib.dos.Process import Process
from .lib.LibList import vamos_libs

from .log import *
from .machine.regs import *
from .machine import CPUState
from .error import *

class Vamos:

  def __init__(self, machine, mem_map, path_mgr):
    self.machine = machine
    self.mem_map = mem_map
    self.mem = machine.get_mem()
    self.raw_mem = self.mem
    self.ram_size = self.mem.get_ram_size_bytes()
    self.cpu = machine.get_cpu()
    self.cpu_type = machine.get_cpu_type()
    self.traps = machine.get_traps()
    self.path_mgr = path_mgr
    self.alloc = mem_map.get_alloc()

  def init(self, binary, arg_str, stack_size, shell, main_cfg):
    # create a label manager and error tracker
    self.label_mgr = self.machine.get_label_mgr()

    # create segment loader
    self.seg_loader = SegmentLoader(self.alloc, self.path_mgr)

    # setup lib manager
    profiler_cfg = self._get_profiler_config(main_cfg)
    self.exec_ctx = ExecLibCtx(self.machine, self.alloc,
                               self.seg_loader, self.path_mgr)
    self.dos_ctx = DosLibCtx(self.machine, self.alloc,
                             self.seg_loader, self.path_mgr,
                             self.run_command, self.start_sub_process)
    libs_cfg = main_cfg.get_libs_dict()
    lib_mgr_cfg = LibMgrCfg.from_dict(libs_cfg)
    self.lib_mgr = LibManager(self.machine, self.alloc, self.seg_loader,
                              lib_mgr_cfg, profiler_cfg=profiler_cfg)
    self.lib_mgr.add_ctx('exec.library', self.exec_ctx)
    self.lib_mgr.add_ctx('dos.library', self.dos_ctx)
    for name in vamos_libs:
      cls = vamos_libs[name]
      self.lib_mgr.add_impl_cls(name, cls)
    self.lib_mgr.bootstrap_exec()

    # no current process right now
    self.process = None
    self.proc_list = []

    self.open_base_libs()
    cwd = str(self.path_mgr.get_cwd())
    return self.setup_main_proc(binary, arg_str, stack_size, shell, cwd)

  def _get_profiler_config(self, main_cfg):
    cfg = main_cfg.get_profile_dict().profile
    names = cfg.libs.names
    if names:
      profiling = True
      all_libs = 'all' in names
    else:
      profiling = False
      all_libs = False
    profiler_cfg = LibProfilerConfig(profiling=profiling,
                                     all_libs=all_libs,
                                     libs=names,
                                     add_samples=cfg.libs.calls,
                                     file=cfg.output.file,
                                     append=cfg.output.append,
                                     dump=cfg.output.dump)
    return profiler_cfg

  def cleanup(self):
    self.cleanup_main_proc()
    self.close_base_libs()
    # shutdown of libmgr needs temp stack
    sp = self.machine.get_ram_begin() - 4
    self.lib_mgr.shutdown(run_sp=sp)

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
    odg = self.mem_map.get_old_dos_guard_base()
    tr.set_ax_l(2, odg)
    tr.set_ax_l(5, odg)
    tr.set_ax_l(6, odg)
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
    odg = self.mem_map.get_old_dos_guard_base()
    tr.set_ax_l(2, odg)
    tr.set_ax_l(5, odg)
    tr.set_ax_l(6, odg)
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
    odg = self.mem_map.get_old_dos_guard_base()
    tr.set_ax_l(2, odg)
    tr.set_ax_l(5, odg)
    tr.set_ax_l(6, odg)
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
    exec_vlib = self.lib_mgr.get_vlib_by_addr(self.exec_addr)
    self.exec_lib = exec_vlib.get_impl()
    # link exec to dos
    self.dos_ctx.set_exec_lib(self.exec_lib)
    # open dos lib
    self.dos_addr = self.lib_mgr.open_lib('dos.library', 0)
    dos_vlib = self.lib_mgr.get_vlib_by_addr(self.dos_addr)
    self.dos_lib = dos_vlib.get_impl()
    self.dos_ctx.set_dos_lib(self.dos_lib)
    # set exec base @4
    self.machine.set_zero_mem(0, self.exec_addr)

  def close_base_libs(self):
    log_main.info("close_base_libs")
    # close dos
    self.lib_mgr.close_lib(self.dos_addr)
    # close exec
    self.lib_mgr.close_lib(self.exec_addr)

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
    odg = self.mem_map.get_old_dos_guard_base()
    regs[REG_A2] = odg
    regs[REG_A5] = odg
    regs[REG_A6] = odg
    return regs

  def cleanup_main_proc(self):
    self.main_proc.free()
