from amitools.vamos.cfgcore import *


class MachineParser(Parser):
    def __init__(self, ini_prefix=None):
        cpus = (
            "68000",
            "68020",
            "68030",
            "68040",
            "000",
            "020",
            "030",
            "040",
            "00",
            "20",
            "30",
            "40",
        )
        hw_access = ("emu", "ignore", "abort", "disable")
        def_cfg = {
            "machine": {
                "cpu": Value(str, "68000", enum=cpus),
                "ram_size": 1024,
            },
            "memmap": {
                "hw_access": Value(str, "emu", enum=hw_access),
                "old_dos_guard": False,
            },
        }
        arg_cfg = {
            "machine": {
                "cpu": Argument(
                    "-C",
                    "--cpu",
                    action="store",
                    help="Set type of CPU to emulate (68000, 68020 or 68040)",
                ),
                "ram_size": Argument(
                    "-m",
                    "--ram-size",
                    action="store",
                    type=int,
                    help="set RAM size in KiB",
                ),
            },
            "memmap": {
                "hw_access": Argument(
                    "-H",
                    "--hw-access",
                    action="store",
                    help="What to do on direct HW access? (emu,ignore,abort,disable)",
                ),
                "old_dos_guard": Argument(
                    "--old-dos-guard",
                    action="store_true",
                    help="Reserve memory range to track access to BCPL addrs",
                ),
            },
        }
        ini_trafo = {
            "machine": {
                "cpu": "cpu",
                "ram_size": "ram_size",
            },
            "memmap": {"hw_access": "hw_access", "old_dos_guard": "old_dos_guard"},
        }
        Parser.__init__(
            self,
            "machine",
            def_cfg,
            arg_cfg,
            "machine",
            "cpu and memory options",
            ini_trafo,
            ini_prefix,
        )
