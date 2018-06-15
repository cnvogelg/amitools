#!/usr/bin/env python2.7
#
# vamos [optoins] <amiga binary> [args ...]
#
# run an m68k AmigaOS binary
#
# written by Christian Vogelgsang (chris@vogelgsang.org)

import os
from amitools.vamos.main import main

if __name__ == '__main__':
  cfg_files = (
      # first look in current dir
      os.path.join(os.getcwd(), ".vamosrc"),
      # then in home dir
      os.path.expanduser("~/.vamosrc"),
  )
  sys.exit(main(cfg_files))
