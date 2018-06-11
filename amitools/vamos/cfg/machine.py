from amitools.vamos.cfgcore import *


class MachineParser(Parser):
  def __init__(self, ini_prefix=None):
    def_cfg = {
        "machine": {
            "cpu": "68000",
            "max_cycles": 0,
            "cycles_per_block": 1000,
            "ram_size": 1024,
            "hw_access": "emu"
        }
    }
    arg_cfg = {
        "machine": {
            "cpu": Argument('-C', '--cpu', action='store',
                            help="Set type of CPU to emulate (68000 or 68020)"),
            "max_cycles": Argument('--max-cycles', action='store', type=int,
                                   help="maximum number of cycles to execute"),
            "cycles_per_block": Argument('--cycles-per-block', action='store',
                                         type=int, help="cycles per block"),
            "ram_size": Argument('-m', '--ram-size', action='store',
                                 type=int, help="set RAM size in KiB"),
            "hw_access": Argument('-H', '--hw-access', action='store',
                                  help="What to do on direct HW access? (emu,ignore,abort,disable)")
        }
    }
    ini_trafo = {
        "machine": {
            "cpu": "cpu",
            "max_cycles": "max_cycles",
            "cycles_per_block": "cycles_per_block",
            "ram_size": "ram_size",
            "hw_access": "hw_access"
        }
    }
    Parser.__init__(self, def_cfg, arg_cfg,
                    "machine", "cpu and memory options",
                    ini_trafo, ini_prefix)
