import sys

from .tool import Tool
from amitools.vamos.cfg import PathParser
from amitools.vamos.path import VamosPathManager, AmiPathError


class PathTool(Tool):
    def __init__(self):
        Tool.__init__(self, "path", "path conversion utilities")
        self.path_parser = None
        self.path_mgr = None

    def add_parsers(self, main_parser):
        self.path_parser = PathParser()
        main_parser.add_parser(self.path_parser)

    def add_args(self, arg_parser):
        sub = arg_parser.add_subparsers(dest="path_cmd")
        # ami2sys
        a2s_parser = sub.add_parser("ami2sys", help="convert Amiga to system path")
        a2s_parser.add_argument("input", help="input path")
        # sys2ami
        s2a_parser = sub.add_parser("sys2ami", help="convert system to Amiga path")
        s2a_parser.add_argument("input", help="input path")

    def setup(self, args):
        self.path_mgr = VamosPathManager()
        cfg_dict = self.path_parser.get_cfg_dict()
        ok = self.path_mgr.parse_config(cfg_dict)
        if not ok:
            return False
        return self.path_mgr.setup()

    def shutdown(self):
        self.path_mgr.shutdown()

    def get_path_mgr(self):
        return self.path_mgr

    def run(self, args):
        cmd = args.path_cmd
        try:
            if cmd == "ami2sys":
                res = self.path_mgr.to_sys_path(args.input)
                return self._report_path(res)
            elif cmd == "sys2ami":
                res = self.path_mgr.from_sys_path(args.input)
                return self._report_path(res)
        except AmiPathError as e:
            print(str(e), file=sys.stderr)
            return 1

    def _report_path(self, path):
        if path is None:
            print("path not found!", file=sys.stderr)
            return 1
        else:
            print(path)
            return 0
