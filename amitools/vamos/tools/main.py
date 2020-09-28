from amitools.vamos.log import log_main, log_setup, log_help
from amitools.vamos.cfgcore import MainParser
from amitools.vamos.cfg import LogParser


def tools_main(tools, cfg_files=None, args=None, cfg_dict=None):
    # no parser given use minimal parser with logging support
    mp = MainParser()
    lp = LogParser()
    mp.add_parser(lp)
    ap = mp.get_arg_parser()

    # single tool?
    if len(tools) == 1:
        single = True
        tool = tools[0]
        tool.add_parsers(mp)
        tool.add_args(ap)
    else:
        single = False
        sp = ap.add_subparsers(dest="tools_cmd")
        for tool in tools:
            sub_parser = sp.add_parser(tool.get_name(), help=tool.get_help())
            tool.add_parsers(mp)
            tool.add_args(sub_parser)

    # --- parse config ---
    if not mp.parse(cfg_files, args, cfg_dict):
        return 1

    # --- init logging ---
    log_cfg = lp.get_cfg_dict().logging
    if not log_setup(log_cfg):
        log_help()
        return 1

    # setup tools
    ap_args = mp.get_args()
    if single:
        if not tool.setup(ap_args):
            log_main.error("tool '%s' failed.", tool.get_name())
            return 1
    else:
        for tool in tools:
            if not tool.setup(ap_args):
                log_main.error("tool '%s' failed.", tool.get_name())
                return 1

    # run tool
    if single:
        result = tool.run(ap_args)
    else:
        result = 1
        for tool in tools:
            if tool.get_name() == ap_args.tools_cmd:
                result = tool.run(ap_args)
                break

    # shutdown
    if single:
        tool.shutdown()
    else:
        for tool in tools:
            tool.shutdown()

    return result
