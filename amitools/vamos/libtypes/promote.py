from amitools.vamos.libstructs import NodeType, LibraryStruct
from .node import Node
from .task import Task
from .process import Process

node_map = {
    NodeType.NT_TASK: Task,
    NodeType.NT_PROCESS: Process,
    NodeType.NT_DEVICE: LibraryStruct,
    NodeType.NT_LIBRARY: LibraryStruct,
}


def promote_type(obj):
    """convert objects according to Amiga rules

    * if its a node then use the node type to derive the actual class
    * if its a task but of type process
    """
    if type(obj) is Node:
        node_type = obj.type.get()
        if node_type in node_map:
            node_cls = node_map[node_type]
            return obj.clone(node_cls)

    # promote a task to a process
    elif type(obj) is Task:
        node_type = obj.node.type.get()
        if node_type == NodeType.NT_PROCESS:
            return obj.clone(Process)

    # no promotion applied
    return obj
