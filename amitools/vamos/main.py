import os

from .cfg import VamosMainParser
from .machine import Machine
from .machine.regs import *
from .log import *
from .Vamos import Vamos
from .lib.dos.SysArgs import *
from .lib.dos.CommandLine import CommandLine
from .path import VamosPathManager

RET_CODE_CONFIG_ERROR = 1000


def main(cfg_files=None, args=None, cfg_dict=None):
  """vamos main entry point.

    setup a vamos session and run it.
    return the error code of the executed Amiga process.

    cfg_files(opt): list/tuple of config files. first found will be read
    args(opt): None=read sys.argv, []=no args, list/tuple=args
    cfg_dict(opt): pass options directly as a dictionary

    if an internal error occurred then return:
      RET_CODE_CONFIG_ERROR (1000): config error
  """
  # retrieve vamos home and data dir
  home_dir = os.path.dirname(__file__)
  data_dir = os.path.join(home_dir, "data")

  # --- new config ---
  mp = VamosMainParser()
  if not mp.parse(cfg_files, args, cfg_dict):
    return RET_CODE_CONFIG_ERROR

  # --- init logging ---
  log_cfg = mp.get_log_dict().logging
  if not log_setup(log_cfg):
    log_help()
    return RET_CODE_CONFIG_ERROR

  # ----- vamos! ---------------------------------------------------------------
  # setup machine
  machine_cfg = mp.get_machine_dict().machine
  use_labels = mp.get_trace_dict().trace.labels
  machine = Machine.from_cfg(machine_cfg, use_labels)
  if not machine:
    return RET_CODE_CONFIG_ERROR

  # setup memory map
  memmap_cfg = mp.get_machine_dict().memmap
  if memmap_cfg.hw_access != "disable":
    max_mem = 0xbf0000 / 1024
    if machine_cfg.ram_size >= max_mem:
      log_main.error("too much RAM requested. max allowed KiB: %d", max_mem)
      return RET_CODE_CONFIG_ERROR

  # setup path manager
  path_mgr = VamosPathManager()
  if not path_mgr.parse_config(mp.get_path_dict()):
    log_main.error("path setup failed!")
    return RET_CODE_CONFIG_ERROR

  # --- proc: binary and arg_str ---
  # a single Amiga-like raw arg was passed
  proc_cfg = mp.get_proc_dict().process
  cmd_cfg = proc_cfg.command
  if cmd_cfg.raw_arg:
    # check args
    if len(cmd_cfg.args) > 0:
      log_main.error("raw arg only allows a single argument!")
      return RET_CODE_CONFIG_ERROR
    # parse raw arg
    cl = CommandLine()
    res = cl.parse_line(cmd_cfg.binary)
    if res != cl.LINE_OK:
      log_main.error("raw arg is invalid! (error %d)", res)
      return RET_CODE_CONFIG_ERROR
    binary = cl.get_cmd()
    arg_str = cl.get_arg_str()
  else:
    # setup binary
    binary = cmd_cfg.binary
    if not cmd_cfg.pure_ami_path:
      # if path exists on host system then make an ami path
      if os.path.exists(binary):
        sys_binary = binary
        binary = path_mgr.from_sys_path(binary)
        if not binary:
          log_main.error("can't map binary: %s", sys_binary)
          return RET_CODE_CONFIG_ERROR
    # combine remaining args to arg_str
    arg_str = sys_args_to_ami_arg_str(cmd_cfg.args)

  # summary
  stack_size = proc_cfg.stack * 1024
  log_main.info("binary: '%s'", binary)
  log_main.info("args:   '%s'", arg_str[:-1])
  log_main.info("stack:  %d", stack_size)

  # combine to vamos instance
  vamos = Vamos(machine, path_mgr)
  if not vamos.init(binary, arg_str, stack_size, cmd_cfg.shell, mp):
    log_main.error("vamos init failed")
    return 1

  # ------ main loop ------

  sp = vamos.get_initial_sp()
  pc = vamos.get_initial_pc()
  get_regs = [REG_D0]
  set_regs = vamos.get_initial_regs()

  # run!
  run_state = machine.run(pc, sp,
                          set_regs=set_regs,
                          get_regs=get_regs,
                          name="main")

  ok = False
  if run_state.done:
    if run_state.error:
      log_main.error("vamos failed!")
      exit_code = 1
    else:
      ok = True
      exit_code = run_state.regs[REG_D0]
      log_main.info("done. exit code=%d", exit_code)
  else:
    log_main.info(
        "vamos was stopped after %d cycles. ignoring result", machine_cfg.max_cycles)
    exit_code = 0

  # shutdown vamos
  if ok:
    vamos.cleanup()

  machine.cleanup()

  # exit
  log_main.info("vamos is exiting")
  return exit_code
