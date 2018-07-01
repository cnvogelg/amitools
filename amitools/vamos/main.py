import os

from .cfg import VamosMainParser
from .machine import Machine, MemoryMap
from .machine.regs import *
from .log import log_main, log_setup
from .Vamos import Vamos
from .path import VamosPathManager
from .trace import TraceManager
from .libmgr import SetupLibManager

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

  # --- parse config ---
  mp = VamosMainParser()
  if not mp.parse(cfg_files, args, cfg_dict):
    return RET_CODE_CONFIG_ERROR

  # --- init logging ---
  log_cfg = mp.get_log_dict().logging
  if not log_setup(log_cfg):
    log_help()
    return RET_CODE_CONFIG_ERROR

  # setup machine
  machine_cfg = mp.get_machine_dict().machine
  use_labels = mp.get_trace_dict().trace.labels
  machine = Machine.from_cfg(machine_cfg, use_labels)
  if not machine:
    return RET_CODE_CONFIG_ERROR

  # setup memory map
  mem_map_cfg = mp.get_machine_dict().memmap
  mem_map = MemoryMap(machine)
  if not mem_map.parse_config(mem_map_cfg):
    log_main.error("memory map setup failed!")
    return RET_CODE_CONFIG_ERROR

  # setup trace manager
  trace_mgr_cfg = mp.get_trace_dict().trace
  trace_mgr = TraceManager(machine)
  if not trace_mgr.parse_config(trace_mgr_cfg):
    log_main.error("tracing setup failed!")
    return RET_CODE_CONFIG_ERROR

  # setup path manager
  path_mgr = VamosPathManager()
  if not path_mgr.parse_config(mp.get_path_dict()):
    log_main.error("path setup failed!")
    return RET_CODE_CONFIG_ERROR

  # legacy vamos instance
  vamos = Vamos(machine, mem_map, path_mgr)

  # setup lib mgr
  slm = SetupLibManager(machine, mem_map, path_mgr)
  if not slm.parse_config(mp):
    log_main.error("lib manager setup failed!")
    return RET_CODE_CONFIG_ERROR
  slm.setup(vamos)
  slm.open_base_libs()

  # legacy quirks
  vamos.dos_ctx = slm.dos_ctx
  vamos.exec_ctx = slm.exec_ctx
  vamos.exec_lib = slm.exec_impl

  # setup main proc
  proc_cfg = mp.get_proc_dict().process
  if not vamos.setup_main_proc(proc_cfg):
    log_main.error("main proc setup failed!")
    return RET_CODE_CONFIG_ERROR

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

  # shutdown main proc
  if ok:
    vamos.cleanup_main_proc()

  # libs shutdown
  slm.close_base_libs()
  slm.cleanup()

  # mem_map and machine shutdown
  if ok:
    mem_map.cleanup()
  machine.cleanup()

  # exit
  log_main.info("vamos is exiting")
  return exit_code
