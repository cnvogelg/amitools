import os

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

  # ----- process handling -----

  def _set_this_task(self, proc):
    """tell exec about this process and all others referencing process from here"""
    self.process = proc
    self.exec_ctx.set_process(proc)
    self.exec_lib.set_this_task(proc)
    self.dos_ctx.set_process(proc)

  def get_current_process(self):
    return self.process

  def run_sub_process(self, proc):
    log_proc.info("start sub process: %s", proc)
    self._set_this_task(proc)

    # setup machine run
    sp = proc.stack_initial
    pc = proc.prog_start

    # new proc registers: d0=arg_len a0=arg_cptr
    # d2=stack_size.  this value is also in 4(sp) (see Process.init_stack), but
    # various C programs rely on it being present (1.3-3.1 at least have it).
    odg = self.mem_map.get_old_dos_guard_base()
    set_regs = {
      REG_D0: proc.arg_len,
      REG_A0: proc.arg_base,
      REG_D2: proc.stack_size,
      REG_A2: odg,
      REG_A5: odg,
      REG_A6: odg
    }
    get_regs = [REG_D0]

    # run machine
    run_state = self.machine.run(pc, sp,
        set_regs=set_regs,
        get_regs=get_regs,
        name="SubProcJump")

    # return value
    ret_code = run_state.regs[REG_D0]
    log_proc.info("return from sub process: ret_code=%d", ret_code)

    # cleanup proc
    proc.free()

    return ret_code

  # ----- overload a process for RunCommand -----

  def run_command(self, start_pc, args_ptr, args_len, stack_size, reg_d1=0):
    newstack      = self.alloc.alloc_memory("RunCommandStack", stack_size)
    newstack_base = newstack.addr
    newstack_top  = newstack_base + stack_size
    oldstack_base = self.process.this_task.access.r_s("pr_Task.tc_SPLower");
    oldstack_top  = self.process.this_task.access.r_s("pr_Task.tc_SPUpper");
    # put stack size on top of stack
    self.mem.w32(newstack_top - 4, stack_size)
    # activate new stack
    self.process.this_task.access.w_s("pr_Task.tc_SPLower", newstack_base)
    self.process.this_task.access.w_s("pr_Task.tc_SPUpper", newstack_top)
    # NOTE: the Manx fexec and BPCL mess is not (yet) setup here.

    # setup machine run
    sp = newstack_top - 8
    pc = start_pc

    # new proc registers: d0=arg_len a0=arg_cptr
    # d2=stack_size.  this value is also in 4(sp) (see Process.init_stack), but
    # various C programs rely on it being present (1.3-3.1 at least have it).
    odg = self.mem_map.get_old_dos_guard_base()
    set_regs = {
      REG_D0: args_len,
      REG_D1: reg_d1,
      REG_A0: args_ptr,
      REG_D2: stack_size,
      REG_A2: odg,
      REG_A5: odg,
      REG_A6: odg
    }
    get_regs = [REG_D0]

    # run machine
    run_state = self.machine.run(pc, sp,
        set_regs=set_regs,
        get_regs=get_regs,
        name="RunCommand")

    # return value
    ret_code = run_state.regs[REG_D0]
    log_proc.info("return from RunCommand: ret_code=%d", ret_code)

    # restore stack values
    self.process.this_task.access.w_s("pr_Task.tc_SPLower", oldstack_base)
    self.process.this_task.access.w_s("pr_Task.tc_SPUpper", oldstack_top)

    # free new stack
    self.alloc.free_memory(newstack)

    # result code
    return ret_code

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
