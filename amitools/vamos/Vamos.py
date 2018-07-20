import os

from amitools.vamos.lib.dos.Process import Process
from .lib.dos.CommandLine import CommandLine
from .lib.dos.SysArgs import sys_args_to_ami_arg_str

from .log import log_proc
from .machine.regs import *
from .schedule import Stack, Task


class Vamos:

  def __init__(self, mem_map, path_mgr):
    self.mem_map = mem_map
    self.path_mgr = path_mgr
    self.alloc = mem_map.get_alloc()

  # ----- process handling -----

  def run_sub_process(self, scheduler, proc):
    log_proc.info("start sub process: %s", proc)

    task = proc.get_task()
    self._add_odg_regs(task)

    scheduler.add_task(task)

    # return value
    run_state = task.get_run_state()
    ret_code = run_state.regs[REG_D0]
    log_proc.info("return from sub process: ret_code=%d", ret_code)

    # cleanup proc
    proc.free()

    return ret_code

  # ----- overload a process for RunCommand -----

  def run_command(self, scheduler, process, start_pc, args_ptr, args_len, stack_size, reg_d1=0):
    new_stack = Stack.alloc(self.alloc, stack_size)
    # save old stack
    oldstack_upper = process.this_task.access.r_s("pr_Task.tc_SPLower")
    oldstack_lower = process.this_task.access.r_s("pr_Task.tc_SPUpper")
    # activate new stack
    process.this_task.access.w_s("pr_Task.tc_SPLower", new_stack.get_upper())
    process.this_task.access.w_s("pr_Task.tc_SPUpper", new_stack.get_lower())
    # NOTE: the Manx fexec and BPCL mess is not (yet) setup here.

    # setup sub task
    sp = new_stack.get_initial_sp()

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
    task = Task("RunCommand", start_pc, new_stack, set_regs, get_regs)

    # run sub task
    scheduler.run_sub_task(task)

    # return value
    run_state = task.get_run_state()
    ret_code = run_state.regs[REG_D0]
    log_proc.info("return from RunCommand: ret_code=%d", ret_code)

    # restore stack values
    process.this_task.access.w_s("pr_Task.tc_SPLower", oldstack_lower)
    process.this_task.access.w_s("pr_Task.tc_SPUpper", oldstack_upper)

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
        return None
      # parse raw arg
      cl = CommandLine()
      res = cl.parse_line(cmd_cfg.binary)
      if res != cl.LINE_OK:
        log_proc.error("raw arg is invalid! (error %d)", res)
        return None
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
            return None
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
      return None
    log_proc.info("set main process: %s", proc)
    # add some regs
    task = proc.get_task()
    self._add_odg_regs(task)
    return proc

  def _add_odg_regs(self, task):
    regs = task.get_start_regs()
    odg = self.mem_map.get_old_dos_guard_base()
    regs[REG_A2] = odg
    regs[REG_A5] = odg
    regs[REG_A6] = odg
