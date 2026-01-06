from amitools.vamos.cfgcore import *


class ScheduleParser(Parser):
    def __init__(self, ini_prefix=None):
        def_cfg = {
            "schedule": {
                "slice_cycles": 100_000,
            }
        }
        arg_cfg = {
            "schedule": {
                "slice_cycles": Argument(
                    "--slice-cycles",
                    action="store",
                    type=int,
                    help="duration of one one scheduler slice in m68k cycles",
                )
            }
        }
        ini_trafo = {
            "schedule": {
                "slice_cycles": "slice_cycles",
            }
        }
        Parser.__init__(
            self,
            "schedule",
            def_cfg,
            arg_cfg,
            "schedule",
            "scheduler options",
            ini_trafo,
            ini_prefix,
        )
