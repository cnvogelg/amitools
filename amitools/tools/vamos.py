#!/usr/bin/env python2.7
#
# vamos [optoins] <amiga binary> [args ...]
#
# run an m68k AmigaOS binary
#
# written by Christian Vogelgsang (chris@vogelgsang.org)

import sys
import argparse
import os

from musashi import m68k
from musashi import emu

import amitools
from amitools.vamos.Log import *
from amitools.vamos.Vamos import Vamos
from amitools.vamos.VamosConfig import VamosConfig
from amitools.vamos.VamosRun import VamosRun
from amitools.vamos.Process import Process

# ----- main -----------------------------------------------------------------
def main():
  # retrieve vamos home and data dir
  home_dir = os.path.dirname(amitools.__file__)
  data_dir = os.path.join(home_dir, "data")

  # --- args --
  parser = argparse.ArgumentParser()
  parser.add_argument('bin', help="AmigaOS binary to run")
  parser.add_argument('args', nargs='*', help="AmigaOS binary arguments")
  # config options
  parser.add_argument('-c', '--config-file', action='store', default=None, help="vamos config file")
  parser.add_argument('-S', '--skip-default-configs', action='store_true', default=False, help="do not read ~/.vamosrc or ./vamosrc")
  # logging config
  parser.add_argument('-l', '--logging', action='store', default=None, help="logging settings: <chan>:<level>,*:<level>,...")
  parser.add_argument('-v', '--verbose', action='store_true', default=None, help="be more verbos")
  parser.add_argument('-q', '--quiet', action='store_true', default=None, help="do not output any logging")
  parser.add_argument('-b', '--benchmark', action='store_true', default=None, help="enable benchmarking")
  parser.add_argument('-L', '--log-file', action='store', default=None, help="write all log messages to a file")
  # low-level tracing
  parser.add_argument('-I', '--instr-trace', action='store_true', default=None, help="enable instruction trace")
  parser.add_argument('-t', '--memory-trace', action='store_true', default=None, help="enable memory tracing (slower)")
  parser.add_argument('-T', '--internal-memory-trace', action='store_true', default=None, help="enable internal memory tracing (slow)")
  parser.add_argument('-r', '--reg-dump', action='store_true', default=None, help="add register dump to instruction trace")
  # cpu emu
  parser.add_argument('-C', '--cpu', action='store', default=None, help="Set type of CPU to emulate (68000 or 68020)")
  parser.add_argument('-y', '--max-cycles', action='store', type=int, default=None, help="maximum number of cycles to execute")
  parser.add_argument('-B', '--cycles-per-block', action='store', type=int, default=None, help="cycles per block")
  # system
  parser.add_argument('-m', '--ram-size', action='store', default=None, type=int, help="set RAM size in KiB")
  parser.add_argument('-s', '--stack-size', action='store', default=None, help="set stack size in KiB")
  parser.add_argument('-H', '--hw-access', action='store', default=None, help="What to do on direct HW access? (emu,ignore,abort,disable)")
  parser.add_argument('-x', '--shell',action='store_true', default=None, help="run an AmigaOs shell instead of a binary")
  # dirs
  parser.add_argument('-D', '--data-dir', action='store', default=None, help="set vamos data directory (default: %s)" % data_dir)
  # lib config
  parser.add_argument('-O', '--lib-options', action='append', default=None, help="set lib options: <lib>:<key>=<value>,...")
  # path config
  parser.add_argument('-a', '--assign', action='append', default=None, help="add AmigaOS assign: name:[+]/sys/path[,/more/path]")
  parser.add_argument('-V', '--volume', action='append', default=None, help="define AmigaOS volume: name:/abs/sys/path")
  parser.add_argument('-A', '--auto-assign', action='store', default=None, help="define auto assign ami path, e.g. vol:/ami/path")
  parser.add_argument('-p', '--path', action='append', default=None, help="define command search ami path, e.g. c:")
  parser.add_argument('-d', '--cwd', action='store', default=None, help="set current working directory")
  parser.add_argument('-P', '--pure-ami-paths', action='store_true', default=None, help="do not allow sys paths for binary")
  args = parser.parse_args()

  # --- init config ---
  cfg = VamosConfig(extra_file=args.config_file, skip_defaults=args.skip_default_configs, args=args, def_data_dir=data_dir)

  # --- init logging ---
  if not log_setup(cfg.logging, cfg.verbose, cfg.quiet, cfg.log_file):
    log_help()
    sys.exit(1)
  cfg.log()

  # ----- vamos! ---------------------------------------------------------------
  # setup CPU
  if cfg.cpu in ('68000', '000', '00'):
    cpu_type = m68k.M68K_CPU_TYPE_68000
  elif cfg.cpu in ('68020', '020', '20'):
    cpu_type = m68k.M68K_CPU_TYPE_68020
  else:
    log_main.error("Invalid CPU type: %s" % cfg.cpu)
    sys.exit(1)
  log_main.info("setting up CPU: %s = %d" % (cfg.cpu, cpu_type))
  cpu = emu.CPU(cpu_type)

  # setup memory
  if cfg.hw_access != "disable":
    max_mem = 0xbf0000 / 1024
    if cfg.ram_size >= max_mem:
      log_main.error("too much RAM requested. max allowed KiB: %d", max_mem)
      sys.exit(1)
  mem = emu.Memory(cfg.ram_size)
  log_main.info("setting up main memory with %s KiB RAM: top=%06x" % (cfg.ram_size, cfg.ram_size * 1024))

  # setup traps
  traps = emu.Traps()

  # combine to vamos instance
  vamos = Vamos(mem, cpu, traps, cfg)
  vamos.init()

  # --- create main process ---
  # setup current working dir
  cwd = args.cwd
  if cwd is None:
    cwd = 'root:' + os.getcwd()

  # prepare binary path
  binary = args.bin
  if not cfg.pure_ami_paths:
    # auto-convert abs paths to root:
    if binary == os.path.abspath(binary):
      binary = 'root:' + binary

  # summary
  log_main.info("bin='%s', args='%s', cwd='%s', shell='%s', stack=%d",
    binary, args.args, cwd, args.shell, cfg.stack_size)

  proc = Process(vamos, binary, args.args, stack_size=cfg.stack_size*1024,
                 shell=args.shell, cwd=cwd)
  if not proc.ok:
    sys.exit(1)
  vamos.set_main_process(proc)

  # ------ main loop ------

  # init cpu and initial registers
  run = VamosRun(vamos, args.benchmark, args.shell)
  run.init()

  # main loop
  exit_code = run.run(cfg.cycles_per_block, cfg.max_cycles)

  # free process
  proc.free()

  # shutdown vamos
  vamos.cleanup()

  # exit
  log_main.info("vamos is exiting")
  return exit_code


if __name__ == '__main__':
  sys.exit(main())
