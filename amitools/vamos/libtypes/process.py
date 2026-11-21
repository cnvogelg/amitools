from amitools.vamos.libstructs import (
    ProcessStruct,
    CLIStruct,
    PathListStruct,
    NodeType,
    MsgPortFlags,
)
from amitools.vamos.astructs import AmigaClassDef

# a process's pr_MsgPort is a real signal port: it is signalled with SIGB_DOS
# (bit 8, reserved per task, see dos/Cli.py and handler/native/startup.py) and
# its task receives the signal. It is not a public port (FindPort() does not
# find it) and not owned by the PortManager.
SIGB_DOS = 8


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
        self.msg_port.new(
            flags=MsgPortFlags.PA_SIGNAL,
            sig_bit=SIGB_DOS,
            sig_task=self.task,
        )
        self.local_vars.new()
