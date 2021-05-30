#!/usr/bin/env python3
#
# vamostool
#
# written by Christian Vogelgsang (chris@vogelgsang.org)

import sys
import os

from amitools.vamos.tools import *


def main(args=None):
    cfg_files = (
        # first look in current dir
        os.path.join(os.getcwd(), ".vamosrc"),
        # then in home dir
        os.path.expanduser("~/.vamosrc"),
    )
    tools = [PathTool(), TypeTool(), LibProfilerTool()]
    return tools_main(tools, cfg_files, args)


if __name__ == "__main__":
    sys.exit(main())
