from amitools.vamos.libstructs import TaskStruct, NodeType, TaskState
from amitools.vamos.astructs import AmigaClassDef
from amitools.vamos.libtypes.process import Process


@AmigaClassDef
class Task(TaskStruct):
    def new_task(self, pri=0, flags=0, nt=NodeType.NT_TASK):
        node = self.node
        node.type.val = nt
        node.pri.val = pri

        self.flags.val = flags
        self.state.val = TaskState.TS_INVALID
        self.mem_entry.new(NodeType.NT_MEMORY)
        self.sig_alloc.val = 0xFFFF

    def promote_type(self):
        """promote task to process if type is set accordingly"""
        node_type = self.node.type.get()
        if node_type == NodeType.NT_PROCESS:
            return self.clone(Process)
        else:
            return self
