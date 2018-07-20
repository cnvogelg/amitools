import os

from amitools.vamos.lib.dos.Process import Process
from .lib.dos.CommandLine import CommandLine
from .lib.dos.SysArgs import sys_args_to_ami_arg_str

from .log import log_proc
from .machine.regs import *
from .schedule import Stack, Task


class Vamos:

  def __init__(self, path_mgr):
    self.path_mgr = path_mgr

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
    return proc
