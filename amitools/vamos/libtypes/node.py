from amitools.vamos.libstructs import NodeStruct, NodeType, MinNodeStruct, LibraryStruct
from amitools.vamos.astructs import AmigaClassDef
from amitools.vamos.libtypes.process import Process
from amitools.vamos.libtypes.task import Task
from amitools.vamos.libtypes.msg import Message, MsgPort


node_map = {
    NodeType.NT_TASK: Task,
    NodeType.NT_PROCESS: Process,
    NodeType.NT_DEVICE: LibraryStruct,
    NodeType.NT_LIBRARY: LibraryStruct,
    NodeType.NT_MESSAGE: Message,
    NodeType.NT_FREEMSG: Message,
    NodeType.NT_REPLYMSG: Message,
    NodeType.NT_MSGPORT: MsgPort,
}


# ln_Succ and ln_Pred of a Node and a MinNode
SUCC = 0
PRED = 4


def remove_node(mem, addr, clear=True):
    """unlink the node at addr as exec's Remove() does"""
    succ = mem.r32(addr + SUCC)
    pred = mem.r32(addr + PRED)
    if succ == 0 or pred == 0:
        return False
    mem.w32(succ + PRED, pred)
    mem.w32(pred + SUCC, succ)
    if clear:
        mem.w32(addr + SUCC, 0)
        mem.w32(addr + PRED, 0)
    return True


class NodeBase:
    # list operations run for every message and task switch: they follow
    # the links in memory instead of through struct wrappers

    def remove(self, clear=True):
        return remove_node(self._mem, self.addr, clear)


@AmigaClassDef
class MinNode(MinNodeStruct, NodeBase):
    """wrap an Exec MinNode in memory an allow to operate on its values."""

    def __str__(self):
        return "[MinNode:@%06x,p=%06x,s=%06x]" % (
            self.addr,
            self.pred.aptr,
            self.succ.aptr,
        )


@AmigaClassDef
class Node(NodeStruct, NodeBase):
    """wrap an Exec Node in memory an allow to operate on its values."""

    def __str__(self):
        return "[Node:@%06x,p=%06x,s=%06x,%s,%d,%s]" % (
            self.addr,
            self.pred.aptr,
            self.succ.aptr,
            self.type,
            self.pri,
            self.name,
        )

    # ----- node ops -----

    def promote_type(self):
        """convert objects according to Amiga rules"""
        node_type = self.type.get()
        if node_type in node_map:
            node_cls = node_map[node_type]
            return self.clone(node_cls)
        else:
            return self

    def find_name(self, name):
        """find name after this node"""
        succ = self.succ.ref
        if succ is None:
            return None
        succ_name = succ.name.str
        if succ_name == name:
            return succ
        return succ.find_name(name)
