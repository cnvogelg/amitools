import os
import argparse

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


def parse_args(data_dir):
  parser = argparse.ArgumentParser()
  parser.add_argument('bin', help="AmigaOS binary to run")
  parser.add_argument('args', nargs='*', help="AmigaOS binary arguments")
  # config options
  parser.add_argument('-c', '--config-file', action='store',
                      default=None, help="vamos config file")
  parser.add_argument('-S', '--skip-default-configs', action='store_true',
                      default=False, help="do not read ~/.vamosrc or ./vamosrc")
  # logging config
  parser.add_argument('-l', '--logging', action='store', default=None,
                      help="logging settings: <chan>:<level>,*:<level>,...")
  parser.add_argument('-v', '--verbose', action='store_true',
                      default=None, help="be more verbos")
  parser.add_argument('-q', '--quiet', action='store_true',
                      default=None, help="do not output any logging")
  parser.add_argument('-L', '--log-file', action='store',
                      default=None, help="write all log messages to a file")
  parser.add_argument('--no-ts', action='store_true',
                      default=False, help="do not log with timestamp")
  # profiling config
  parser.add_argument('--profile', action='store_true',
                      default=None, help="collect call infos of vamos libs")
  parser.add_argument('--profile-samples', action='store_true',
                      default=None, help="store each lib call individually")
  parser.add_argument('--profile-libs', action='store',
                      default=None, help="lib/dev name list to profile")
  parser.add_argument('--profile-all-libs', action='store_true',
                      default=None, help="profile all vamos libraries and devices")
  parser.add_argument('--profile-file-append', action='store_true',
                      default=None, help="if profile file exists add data")
  parser.add_argument('--profile-file', action='store',
                      default=None, help="file name for profile data")
  parser.add_argument('--profile-dump', action='store_true',
                      default=None, help="dump the profile result to log")
  # low-level tracing
  parser.add_argument('-I', '--instr-trace', action='store_true',
                      default=None, help="enable instruction trace")
  parser.add_argument('-t', '--memory-trace', action='store_true',
                      default=None, help="enable memory tracing (slower)")
  parser.add_argument('-T', '--internal-memory-trace', action='store_true',
                      default=None, help="enable internal memory tracing (slow)")
  parser.add_argument('-r', '--reg-dump', action='store_true',
                      default=None, help="add register dump to instruction trace")
  parser.add_argument('-B', '--labels', action='store_true',
                      default=None, help="add memory labels for detailed infos")
  # cpu emu
  parser.add_argument('-C', '--cpu', action='store', default=None,
                      help="Set type of CPU to emulate (68000 or 68020)")
  parser.add_argument('--max-cycles', action='store', type=int,
                      default=None, help="maximum number of cycles to execute")
  parser.add_argument('--cycles-per-block', action='store',
                      type=int, default=None, help="cycles per block")
  # system
  parser.add_argument('-m', '--ram-size', action='store',
                      default=None, type=int, help="set RAM size in KiB")
  parser.add_argument('-s', '--stack-size', action='store',
                      default=None, help="set stack size in KiB")
  parser.add_argument('-H', '--hw-access', action='store', default=None,
                      help="What to do on direct HW access? (emu,ignore,abort,disable)")
  parser.add_argument('-x', '--shell', action='store_true',
                      default=None, help="run an AmigaOs shell instead of a binary")
  # dirs
  parser.add_argument('-D', '--data-dir', action='store', default=None,
                      help="set vamos data directory (default: %s)" % data_dir)
  # lib config
  parser.add_argument('-O', '--lib-options', action='append',
                      default=None, help="set lib options: <lib>+<key>=<value>,...")
  # path config
  parser.add_argument('-a', '--assign', action='append', default=None,
                      help="add AmigaOS assign: name:[+]/sys/path[,/more/path]")
  parser.add_argument('-V', '--volume', action='append', default=None,
                      help="define AmigaOS volume: name:/abs/sys/path")
  parser.add_argument('-A', '--auto-assign', action='store', default=None,
                      help="define auto assign ami path, e.g. vol:/ami/path")
  parser.add_argument('-p', '--path', action='append', default=None,
                      help="define command search ami path, e.g. c:")
  parser.add_argument('-d', '--cwd', action='store',
                      default=None, help="set current working directory")
  # arg handling
  parser.add_argument('-P', '--pure-ami-paths', action='store_true',
                      default=None, help="do not allow sys paths for binary")
  parser.add_argument('-R', '--raw-arg', action='store_true',
                      default=None, help="pass a single unmodified argument string")
  return parser.parse_args()
