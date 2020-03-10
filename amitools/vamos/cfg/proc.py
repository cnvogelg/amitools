from amitools.vamos.cfgcore import *


class ProcessParser(Parser):
    def __init__(self, ini_prefix=None):
        def_cfg = {
            "process": {
                "command": {
                    "binary": Value(str),
                    "args": ValueList(str, allow_split=False),
                    "shell": False,
                    "pure_ami_path": False,
                    "raw_arg": False,
                },
                "stack": 8,
            }
        }
        arg_cfg = {
            "process": {
                "command": {
                    "binary": Argument("bin", help="AmigaOS binary to run", order=1),
                    "args": Argument(
                        "args", nargs="*", help="AmigaOS binary arguments", order=2
                    ),
                    "shell": Argument(
                        "-x",
                        "--shell",
                        action="store_true",
                        help="run an AmigaOs shell instead of a binary",
                    ),
                    "pure_ami_path": Argument(
                        "-P",
                        "--pure-ami-paths",
                        action="store_true",
                        help="do not allow sys paths for binary",
                    ),
                    "raw_arg": Argument(
                        "-R",
                        "--raw-arg",
                        action="store_true",
                        help="pass a single unmodified argument string",
                    ),
                },
                "stack": Argument(
                    "-s",
                    "--stack-size",
                    action="store",
                    type=int,
                    help="set stack size in KiB",
                ),
            }
        }
        ini_trafo = {
            "process": {
                "command": {
                    "shell": "shell",
                    "pure_ami_path": "pure_ami_paths",
                    "raw_arg": "raw_arg",
                },
                "stack": "stack_size",
            }
        }
        Parser.__init__(
            self,
            "proc",
            def_cfg,
            arg_cfg,
            "process",
            "command process options",
            ini_trafo,
            ini_prefix,
        )
