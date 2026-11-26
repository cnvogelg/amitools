from ..cfgcore import Argument, Parser, ValueList


class CommandParser(Parser):
    def __init__(self):
        def_cfg = {
            "command": {
                "resident_dir": ValueList(str),
                "no_internal_commands": False,
            }
        }
        arg_cfg = {
            "command": {
                "resident_dir": Argument(
                    "--resident-dir",
                    action="append",
                    help="register every *.py in DIR as a resident command",
                ),
                "no_internal_commands": Argument(
                    "--no-internal-commands",
                    action="store_true",
                    help="do not register the built-in vamos.command commands",
                ),
            }
        }
        Parser.__init__(
            self, "command", def_cfg, arg_cfg, "command", "python command options"
        )
