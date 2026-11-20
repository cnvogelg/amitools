from amitools.vamos.cfgcore import *


class DiskParser(Parser):
    def __init__(self):
        def_cfg = {
            "disks": ValueList(str, allow_split=False),
            "read_only": True,
        }
        arg_cfg = {
            "disks": Argument(
                "--disk",
                action="append",
                help="expose a disk image through an Amiga device",
            ),
            "read_only": Argument(
                "--disk-read-write",
                action="store_false",
                help="open --disk images read-write instead of read-only",
            ),
        }
        Parser.__init__(
            self,
            "disk",
            def_cfg,
            arg_cfg,
            "disks",
            "configure Amiga disk images",
        )
