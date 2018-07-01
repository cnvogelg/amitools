import os

from Trampoline import Trampoline
from amitools.vamos.lib.dos.Process import Process
from .lib.dos.CommandLine import CommandLine
from .lib.dos.SysArgs import sys_args_to_ami_arg_str

from .log import log_proc
from .machine.regs import *

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
    # no current process right now
    self.process = None
    self.proc_list = []

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

  # ----- main process -----

  def setup_main_proc(self, proc_cfg):
    # a single Amiga-like raw arg was passed
    cmd_cfg = proc_cfg.command
    if cmd_cfg.raw_arg:
      # check args
      if len(cmd_cfg.args) > 0:
        log_proc.error("raw arg only allows a single argument!")
        return False
      # parse raw arg
      cl = CommandLine()
      res = cl.parse_line(cmd_cfg.binary)
      if res != cl.LINE_OK:
        log_proc.error("raw arg is invalid! (error %d)", res)
        return False
      binary = cl.get_cmd()
      arg_str = cl.get_arg_str()
    else:
      # setup binary
      binary = cmd_cfg.binary
      if not cmd_cfg.pure_ami_path:
        # if path exists on host system then make an ami path
        if os.path.exists(binary):
          sys_binary = binary
          binary = self.path_mgr.from_sys_path(binary)
          if not binary:
            log_proc.error("can't map binary: %s", sys_binary)
            return False
      # combine remaining args to arg_str
      arg_str = sys_args_to_ami_arg_str(cmd_cfg.args)

    # summary
    stack_size = proc_cfg.stack * 1024
    shell = proc_cfg.command.shell
    log_proc.info("binary: '%s'", binary)
    log_proc.info("args:   '%s'", arg_str[:-1])
    log_proc.info("stack:  %d", stack_size)

    cwd = str(self.path_mgr.get_cwd())
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
