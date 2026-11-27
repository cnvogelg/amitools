from amitools.vamos.astructs import CSTR
from amitools.vamos.libtypes import List, MinList, Node
from amitools.vamos.log import log_exec


class ListMixin:
    """exec.library list LVOs (fd banner: lists)."""

    def NewMinList(self, ctx, minlist: MinList):
        minlist.new()
        log_exec.info("NewMinList(0x%06x)", minlist.addr)
        return minlist.addr

    def AddTail(self, ctx, list: List, node: Node):
        log_exec.info("AddTail(%s, %s)", list, node)
        list.add_tail(node)
        log_exec.debug("-> %s", list)

    def AddHead(self, ctx, list: List, node: Node):
        log_exec.info("AddHead(%s, %s)", list, node)
        list.add_head(node)
        log_exec.debug("-> %s", list)

    def RemHead(self, ctx, list: List) -> Node:
        node = list.rem_head()
        log_exec.info("RemHead(%s) -> %s", list, node)
        return node

    def RemTail(self, ctx, list: List) -> Node:
        node = list.rem_tail()
        log_exec.info("RemTail(%s) -> %s", list, node)
        return node

    def FindName(self, ctx, list: List, name: CSTR) -> Node:
        node = list.find_name(name.str)
        log_exec.info("FindName(%s, %s) -> %s", list, name, node)
        return node

    def Insert(self, ctx, list: List, node: Node, list_node: Node):
        list.insert(node, list_node)
        log_exec.info("Insert(%s, %s, %s)", list, node, list_node)

    def Enqueue(self, ctx, list: List, node: Node):
        list.enqueue(node)
        log_exec.info("Enqueue(%s, %s)", list, node)

    def Remove(self, ctx, node: Node):
        log_exec.info("Remove(%s)", node)
        ok = node.remove()
        if not ok:
            log_exec.warning("Remove(%s) not in a list?", node)
