from amitools.vamos.log import log_mode
from .proc import ProcMode
from .test import TestMode


class ModeSetup:
    mode_map = {
        "proc": ProcMode,
        "test": TestMode,
    }

    @classmethod
    def help(cls):
        print("available modes:")
        for name in sorted(cls.mode_map.keys()):
            print(name)

    @classmethod
    def select(cls, cmd_cfg):
        # get configured mode
        mode = cmd_cfg.mode
        log_mode.info("select mode '%s'", mode)

        # is mode available
        if mode in cls.mode_map:
            return cls.mode_map[mode]()
        else:
            cls.help()
