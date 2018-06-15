from amitools.vamos.cfgcore import *


class MachineParser(Parser):
  def __init__(self, ini_prefix=None):
    cpus = ('68000', '68020', '68030',
            '000', '020', '030',
            '00', '20', '30')
    hw_access = ('emu', 'ignore', 'abort', 'disable')
    def_cfg = {
        "machine": {
            "cpu": Value(str, "68000", enum=cpus),
            "max_cycles": 0,
            "cycles_per_block": 1000,
            "ram_size": 1024,
            "hw_access": Value(str, "emu", enum=hw_access)
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
    Parser.__init__(self, "machine", def_cfg, arg_cfg,
                    "machine", "cpu and memory options",
                    ini_trafo, ini_prefix)
