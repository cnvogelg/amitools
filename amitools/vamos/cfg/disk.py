from amitools.vamos.cfgcore import *


class DiskParser(Parser):
    def __init__(self):
        def_cfg = {
            "disks": ValueList(str, allow_split=False),
        }
        arg_cfg = {
            "disks": Argument(
                "--disk",
                action="append",
                help="expose a disk image through an Amiga device",
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
