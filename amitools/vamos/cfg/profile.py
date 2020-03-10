from amitools.vamos.cfgcore import *


class ProfileParser(Parser):
    def __init__(self):
        def_cfg = {
            "profile": {
                "enabled": False,
                "libs": {"names": ValueList(str), "calls": False},
                "output": {"file": Value(str), "append": False, "dump": False},
            }
        }
        arg_cfg = {
            "profile": {
                "enabled": Argument(
                    "--profile", action="store_true", help="enable vamos profiler"
                ),
                "libs": {
                    "names": Argument(
                        "--profile-libs",
                        action="append",
                        help="lib/dev name list to profile or 'all'",
                    ),
                    "calls": Argument(
                        "--profile-lib-calls",
                        action="store_true",
                        help="store each lib call individually",
                    ),
                },
                "output": {
                    "file": Argument(
                        "--profile-file",
                        action="store",
                        help="file name for profile data",
                    ),
                    "append": Argument(
                        "--profile-file-append",
                        action="store_true",
                        help="if profile file exists add data",
                    ),
                    "dump": Argument(
                        "--profile-dump",
                        action="store_true",
                        help="dump the profile result to log",
                    ),
                },
            }
        }
        Parser.__init__(
            self, "profile", def_cfg, arg_cfg, "profile", "profiling options"
        )
