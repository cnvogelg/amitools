from amitools.vamos.libstructs import NodeStruct, MinNodeStruct
from amitools.vamos.astructs import AmigaClassDef


class NodeBase:
    def remove(self, clear=True):
        succ = self.succ.ref
        pred = self.pred.ref
        if succ is None or pred is None:
            raise ValueError("remove node without succ/pred!")
        succ.pred.ref = pred
        pred.succ.ref = succ
        if clear:
            self.succ.ref = None
            self.pred.ref = None


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
        return "[Node:@%06x,p=%06x,s=%06x,%s,%d,'%s']" % (
            self.addr,
            self.pred.aptr,
            self.succ.aptr,
            self.type,
            self.pri,
            self.name,
        )

    # ----- node ops -----

    def find_name(self, name):
        """find name after this node"""
        succ = self.succ.ref
        if succ is None:
            return None
        succ_name = succ.name.str
        if succ_name == name:
            return succ
        return succ.find_name(name)
