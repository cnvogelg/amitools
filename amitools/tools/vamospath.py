#!/usr/bin/env python2.7
#
# vamospath [options] <path>
#
# a tool to convert between AmigaOS and native paths
#

import argparse
import os

from amitools.vamos.log import *
from amitools.vamos.VamosConfig import *
from amitools.vamos.path import PathManager
from amitools.vamos.lib.dos.PathMatch import PathMatch

def main():
  # --- args ---
  parser = argparse.ArgumentParser()
  parser.add_argument('op', help="path operation: a2s s2a abs parent current name")
  parser.add_argument('arg', help="path to convert")
  parser.add_argument('-v', '--verbose', action='store_true', default=False, help="be more verbos")
  parser.add_argument('-l', '--logging', action='store', default=None, help="logging settings: <chan>:<level>,*:<level>,...")
  parser.add_argument('-c', '--config-file', action='store', default=None, help="vamos config file")
  parser.add_argument('-a', '--assign', action='append', default=None, help="define AmigaOS assign: name:[+]vol:/ami/path[,vol2:/more/path]")
  parser.add_argument('-V', '--volume', action='append', default=None, help="define AmigaOS volume: name:/abs/sys/path")
  parser.add_argument('-A', '--auto-assign', action='store', default=None, help="define auto assign ami path, e.g. vol:/ami/path")
  parser.add_argument('-p', '--path', action='append', default=None, help="define command search ami path, e.g. c:")
  args = parser.parse_args()

  # --- setup logging ---
  log_setup(args.logging,verbose=args.verbose)

  # --- setup config ---
  cfg = VamosConfig(extra_file=args.config_file, args=args)

  # --- setup path manager ---
  pm = PathManager(cfg)

  # --- main ---
  op = args.op
  if op == 'a2s':
    print pm.ami_to_sys_path(args.arg)
  elif op == 's2a':
    print pm.sys_to_ami_path(args.arg)

  elif op == 'abs':
    print pm.ami_abs_path(args.arg)
  elif op == 'parent':
    print pm.ami_abs_parent_path(args.arg)
  elif op == 'current':
    print pm.ami_abs_cur_path()
  # path components
  elif op == 'name':
    print pm.ami_name_of_path(args.arg)
  elif op == 'dir':
    print pm.ami_dir_of_path(args.arg)
  elif op == 'volume':
    print pm.ami_volume_of_path(args.arg)
  elif op == 'voldir':
    print pm.ami_voldir_of_path(args.arg)
  # path query
  elif op == 'cmd':
    print pm.ami_command_to_sys_path(args.arg)
  # list
  elif op == 'list':
    print pm.ami_list_dir(args.arg)
  # match path
  elif op == 'match':
    matcher = PathMatch(pm)
    ok = matcher.parse(args.arg)
    if ok:
      print matcher
      match = matcher.begin()
      while match != None:
        print match
        match = matcher.next()
  # assign manager
  elif op == 'assign':
    print pm.assign_mgr.ami_path_resolve(args.arg)
  elif op == 'resolve':
    print pm.assign_mgr.ami_path_resolve_assigns(args.arg)
  elif op == 'auto':
    print pm.assign_mgr.ami_path_resolve_auto_assigns(args.arg)
  # volume manager ops
  elif op == 'v_s2a':
    print pm.vol_mgr.sys_to_ami_path(args.arg)
  elif op == 'v_a2s':
    print pm.vol_mgr.ami_to_sys_path(args.arg)
  # unknown operation
  else:
    print "INVALID OPERATION:",op
  return 0


if __name__ == '__main__':
  sys.exit(main())
