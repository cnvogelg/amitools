from __future__ import print_function
import sys

from amitools.vamos.cfgcore import *
from amitools.vamos.cfg import *
from amitools.vamos.log import log_main, log_setup
from amitools.vamos.path import VamosPathManager, AmiPathError


class MainPathParser(MainParser):
  def __init__(self, debug=None, *args, **kwargs):
    MainParser.__init__(self, debug, *args, **kwargs)
    # log
    self.log = LogParser('vamos')
    self.add_parser(self.log)
    # path
    self.path = PathParser()
    self.add_parser(self.path)

  def get_log_dict(self):
    return self.log.get_cfg_dict()

  def get_path_dict(self):
    return self.path.get_cfg_dict()


def add_path_args(arg_parse):
  sub = arg_parse.add_subparsers(dest='path_cmd')
  # ami2sys
  a2s_parser = sub.add_parser('ami2sys',
                              help='convert Amiga to system path')
  a2s_parser.add_argument('input', help='input path')
  # sys2ami
  s2a_parser = sub.add_parser('sys2ami',
                              help='convert system to Amiga path')
  s2a_parser.add_argument('input', help='input path')


def report_path(path):
  if path is None:
    print("path not found!", file=sys.stderr)
    return 1
  else:
    print(path)
    return 0


def path_main(cfg_files=None, args=None, cfg_dict=None):
  # --- parse config ---
  mp = MainPathParser()
  add_path_args(mp.get_arg_parser())
  if not mp.parse(cfg_files, args, cfg_dict):
    return 1

  # --- init logging ---
  log_cfg = mp.get_log_dict().logging
  if not log_setup(log_cfg):
    log_help()
    return 1

  # setup path manager
  path_mgr = VamosPathManager()
  if not path_mgr.parse_config(mp.get_path_dict()):
    log_main.error("path setup failed!")
    return 1

  # parse my args
  args = mp.get_args()
  cmd = args.path_cmd
  try:
    if cmd == 'ami2sys':
      res = path_mgr.to_sys_path(args.input)
      return report_path(res)
    elif cmd == 'sys2ami':
      res = path_mgr.from_sys_path(args.input)
      return report_path(res)
  except AmiPathError as e:
    print(str(e), file=sys.stderr)
    return 1
