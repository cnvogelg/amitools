from amitools.vamos.cfgcore import *


class LogParser(Parser):
    def __init__(self, ini_prefix=None):
        levels = ("debug", "info", "warn", "error", "fatal", "off")
        def_cfg = {
            "logging": {
                "levels": ValueDict(str, enum=levels),
                "file": Value(str),
                "verbose": False,
                "quiet": False,
                "timestamps": True,
            }
        }
        arg_cfg = {
            "logging": {
                "levels": Argument(
                    "-l",
                    "--logging",
                    action="store",
                    help="logging settings: <chan>:<level>,*:<level>,...",
                ),
                "file": Argument(
                    "-L",
                    "--log-file",
                    action="store",
                    help="write all log messages to a file",
                ),
                "verbose": Argument(
                    "-v", "--verbose", action="store_true", help="be more verbos"
                ),
                "quiet": Argument(
                    "-q",
                    "--quiet",
                    action="store_true",
                    help="do not output any logging",
                ),
                "timestamps": Argument(
                    "--no-ts", action="store_false", help="do not log with timestamp"
                ),
            }
        }
        ini_trafo = {
            "logging": {
                "levels": "logging",
                "file": "log_file",
                "verbose": "verbose",
                "quiet": "quiet",
            }
        }
        Parser.__init__(
            self,
            "log",
            def_cfg,
            arg_cfg,
            "logging",
            "enable logging channels, write to file",
            ini_trafo,
            ini_prefix,
        )
