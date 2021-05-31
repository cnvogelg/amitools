#!/usr/bin/env python3
#
# typetool [options] <path>
#
# a tool to inspect types
#

import sys
import os

from amitools.vamos.tools import tools_main, TypeTool


def main(args=None):
    cfg_files = (
        # first look in current dir
        os.path.join(os.getcwd(), ".vamosrc"),
        # then in home dir
        os.path.expanduser("~/.vamosrc"),
    )
    tools = [TypeTool()]
    return tools_main(tools, cfg_files, args)


if __name__ == "__main__":
    sys.exit(main())
