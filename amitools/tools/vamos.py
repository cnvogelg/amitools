#!/usr/bin/env python3
#
# vamos [optoins] <amiga binary> [args ...]
#
# run an m68k AmigaOS binary
#
# written by Christian Vogelgsang (chris@vogelgsang.org)

import os
import sys
from amitools.vamos.main import main as vmain
from amitools.vamos.main import main_profile


def main(args=None):
    cfg_files = (
        # first look in current dir
        os.path.join(os.getcwd(), ".vamosrc"),
        # then in home dir
        os.path.expanduser("~/.vamosrc"),
    )
    # profile run?
    if "VAMOS_PROFILE" in os.environ:
        vamos_profile = os.environ["VAMOS_PROFILE"]
        if vamos_profile == "dump":
            profile_file = None
        else:
            profile_file = vamos_profile
        ret_code = main_profile(
            cfg_files, args=args, profile_file=profile_file, dump_profile=True
        )
    # regular run
    else:
        ret_code = vmain(cfg_files, args=args)
    return ret_code


if __name__ == "__main__":
    sys.exit(main())
