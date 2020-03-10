from amitools.vamos.cfgcore import *
from amitools.vamos.cfg import *


class VamosMainParser(MainParser):
    def __init__(self, debug=None, *args, **kwargs):
        MainParser.__init__(self, debug, *args, **kwargs)
        # log
        self.log = LogParser("vamos")
        self.add_parser(self.log)
        # path
        self.path = PathParser()
        self.add_parser(self.path)
        # libs
        self.libs = LibsParser()
        self.add_parser(self.libs)
        # trace
        self.trace = TraceParser("vamos")
        self.add_parser(self.trace)
        # machine
        self.machine = MachineParser("vamos")
        self.add_parser(self.machine)
        # proc
        self.proc = ProcessParser("vamos")
        self.add_parser(self.proc)
        # profile
        self.profile = ProfileParser()
        self.add_parser(self.profile)

    def get_log_dict(self):
        return self.log.get_cfg_dict()

    def get_path_dict(self):
        return self.path.get_cfg_dict()

    def get_libs_dict(self):
        return self.libs.get_cfg_dict()

    def get_trace_dict(self):
        return self.trace.get_cfg_dict()

    def get_machine_dict(self):
        return self.machine.get_cfg_dict()

    def get_proc_dict(self):
        return self.proc.get_cfg_dict()

    def get_profile_dict(self):
        return self.profile.get_cfg_dict()
