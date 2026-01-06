from amitools.vamos.cfgcore import *


class MachineParser(Parser):
    def __init__(self, ini_prefix=None):
        backend_keys = (
            "name",
            "host",
            "port",
        )
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
        hw_exc_names = (
            "bus",
            "address",
            "illegal",
            "zero_div",
            "chk",
            "trapv",
            "priv",
            "trace",
            "line_a",
            "line_f",
            "irqs",
            "traps",
        )
        hw_exc_modes = ("ignore", "log", "abort")
        def_cfg = {
            "machine": {
                "backend": ValueDict(str, valid_keys=backend_keys),
                "cpu": Value(str, "68000", enum=cpus),
                "ram_size": 1024,
                "hw_exc": ValueDict(
                    str,
                    valid_keys=hw_exc_names,
                    enum=hw_exc_modes,
                ),
            },
            "memmap": {
                "hw_access": Value(str, "emu", enum=hw_access),
                "old_dos_guard": False,
            },
        }
        arg_cfg = {
            "machine": {
                "backend": Argument(
                    "-b",
                    "--backend",
                    action="store",
                    help="Set machine emulation backend",
                ),
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
                "hw_exc": Argument(
                    "-e",
                    "--hw-exception",
                    action="store",
                    help="Set CPU HW Exception handling",
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
                "backend": "backend",
                "cpu": "cpu",
                "ram_size": "ram_size",
                "hw_exc": "hw_exc",
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
