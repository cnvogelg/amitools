from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.libstructs import NodeType
from amitools.vamos.libtypes import promote_type, Node, Task, Process
from amitools.vamos.libtypes.promote import node_map


def libtypes_promote_node_test():
    mem = MockMemory()
    for node_type, node_cls in node_map.items():
        node = Node(mem, 0x40)
        node.type.set(node_type)
        new_node = promote_type(node)
        assert type(new_node) is node_cls


def libtypes_promote_task_test():
    mem = MockMemory()
    task = Task(mem, 0x40)
    task.node.type.set(NodeType.NT_PROCESS)
    proc = promote_type(task)
    assert type(proc) is Process
