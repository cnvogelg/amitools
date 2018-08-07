#!/usr/bin/env python2.7
#
# vamospath [options] <path>
#
# a tool to convert between AmigaOS and native paths
#

import sys
import os

from amitools.vamos.tools.path import path_main


def main():
  cfg_files = (
      # first look in current dir
      os.path.join(os.getcwd(), ".vamosrc"),
      # then in home dir
      os.path.expanduser("~/.vamosrc"),
  )
  sys.exit(path_main(cfg_files))


if __name__ == '__main__':
  sys.exit(main())
