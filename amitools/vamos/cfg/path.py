from amitools.vamos.cfgcore import *


class PathParser(Parser):
  def __init__(self):
    def_cfg = {
        "path": {
            "command": ValueList(str),
            "cwd": Value(str)
        },
        "assigns": ValueDict(ValueList(str, sep='+')),
        "volumes": ValueDict(str)
    }
    arg_cfg = {
        "path": {
            "command": Argument('-p', '--path', action='append',
                                help="define command search ami path, e.g. c:,sc:c"),
            "cwd": Argument('--cwd', action='store',
                            help="set the current working directory")
        },
        "assigns": Argument('-a', '--assign', action='append',
                            help="add AmigaOS assign: name:/sys/path[+/more/path]"),
        "volumes": Argument('-V', '--volume', action='append',
                            help="define AmigaOS volume: name:/abs/sys/path")
    }
    ini_trafo = {
        "assigns": "assigns",
        "volumes": "volumes",
        "path": {
            "command": ["path", "path"],
            "cwd": ["path", "cwd"]
        }
    }
    Parser.__init__(self, "path", def_cfg, arg_cfg,
                    "paths", "define volumes, assigns, and the search path",
                    ini_trafo)
