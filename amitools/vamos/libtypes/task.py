from amitools.vamos.libstructs import TaskStruct, NodeType, TaskState
from amitools.vamos.astructs import AmigaClassDef


@AmigaClassDef
class Task(TaskStruct):
    def new_task(self, pri=0, flags=0, nt=NodeType.NT_TASK):
        node = self.node
        node.type.val = nt
        node.pri.val = pri

        self.flags.val = flags
        self.state.val = TaskState.TS_INVALID
        self.mem_entry.new_list(NodeType.NT_MEMORY)
