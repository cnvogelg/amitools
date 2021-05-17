from amitools.vamos.libstructs import ProcessStruct, CLIStruct, PathListStruct, NodeType
from amitools.vamos.astructs import AmigaClassDef


@AmigaClassDef
class PathList(PathListStruct):
    pass


@AmigaClassDef
class CLI(CLIStruct):
    pass


@AmigaClassDef
class Process(ProcessStruct):
    def new_proc(self):
        self.task.new_task(nt=NodeType.NT_PROCESS)
        self.msg_port.new_port()
        self.local_vars.new_list()
