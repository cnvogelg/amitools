from amitools.vamos.cfgcore import ConfigDict
from amitools.vamos.mode.proc import ProcMode


def proc_mode_raw_arg_test():
    cmd_cfg = ConfigDict({"raw_arg": True})

    result = ProcMode().get_cmd_args(None, cmd_cfg, ['program "two words"'])

    assert result == ("program", '"two words"\n')
