from amitools.vamos.libstructs import ListStruct, MinListStruct
from amitools.vamos.astructs import AmigaClassDef
from .node import Node, MinNode, SUCC, PRED, remove_node

# lh_Head, lh_Tail and lh_TailPred of a List and a MinList
_HEAD = 0
_TAIL = 4
_TAIL_PRED = 8


class ListIter(object):
    def __init__(self, alist, start_node=None, promote=False):
        self.alist = alist
        self.mem = self.alist._mem
        self.promote = promote
        if start_node is None:
            self.node_type = alist._node_type
            # an uninitialized list may start with a NULL node
            self.addr = alist._start_addr()
        else:
            self.node_type = type(start_node)
            self.addr = start_node.addr

    def __iter__(self):
        return self

    def __next__(self):
        addr = self.addr
        if addr == 0:
            raise StopIteration()
        succ = self.mem.r32(addr + SUCC)
        if succ == 0:
            raise StopIteration()
        self.addr = succ
        res = self.node_type(self.mem, addr)
        if self.promote:
            return res.promote_type()
        else:
            return res


def list_add_head(mem, list_addr, node_addr):
    """prepend a node to the list at list_addr as exec's AddHead() does"""
    head = list_addr + _HEAD
    n = mem.r32(head + SUCC)
    mem.w32(node_addr + PRED, head)
    mem.w32(node_addr + SUCC, n)
    mem.w32(head + SUCC, node_addr)
    # an uninitialized list: emulate the NULL pointer write of exec
    # AddHead, h->ln_Pred = node, at addr 0 + offset of ln_Pred
    mem.w32(n + PRED, node_addr)


def list_add_tail(mem, list_addr, node_addr):
    """append a node to the list at list_addr as exec's AddTail() does"""
    tail = list_addr + _TAIL
    tp = mem.r32(list_addr + _TAIL_PRED)
    mem.w32(node_addr + SUCC, tail)
    mem.w32(tail + PRED, node_addr)
    mem.w32(node_addr + PRED, tp)
    # an uninitialized list: emulate the NULL pointer write of exec
    # AddTail, tp->ln_Succ = node, at addr 0 + offset of ln_Succ
    mem.w32(tp + SUCC, node_addr)


def list_first(mem, list_addr):
    """address of the list's first node, or 0 for an empty list"""
    addr = mem.r32(list_addr + _HEAD)
    if addr == 0 or mem.r32(addr + SUCC) == 0:
        return 0
    return addr


def list_rem_head(mem, list_addr):
    """unlink the list's first node and return its address, or 0"""
    addr = list_first(mem, list_addr)
    if addr != 0:
        remove_node(mem, addr)
    return addr


class ListBase:
    # the head and the tail node overlap in the list header
    @property
    def _head(self):
        return self._node_type(self._mem, self.addr + _HEAD)

    @property
    def _tail(self):
        return self._node_type(self._mem, self.addr + _TAIL)

    def _node(self, addr):
        return self._node_type(self._mem, addr)

    def _start_addr(self):
        """address of the first node to iterate over, or 0"""
        addr = self._mem.r32(self.addr + _HEAD)
        if addr == 0:
            # uninitialized list with a NULL lh_Head: real m68k code
            # would dereference it and read ln_Succ at addr 0.
            # AddTail/AddHead on such a list store the node there.
            addr = self._mem.r32(0)
        return addr

    def _iter_start_node(self):
        """return the first node to iterate over"""
        addr = self._start_addr()
        return self._node(addr) if addr != 0 else None

    def __iter__(self):
        return ListIter(self)

    def __len__(self):
        mem = self._mem
        l = 0
        addr = self._start_addr()
        while addr != 0:
            addr = mem.r32(addr + SUCC)
            if addr == 0:
                break
            l += 1
        return l

    def is_empty(self):
        addr = self._start_addr()
        return addr == 0 or self._mem.r32(addr + SUCC) == 0

    def to_list(self, promote=False):
        return [a for a in ListIter(self, promote=promote)]

    def iter_at(self, node, promote=False):
        return ListIter(self, start_node=node, promote=promote)

    def add_head(self, node):
        list_add_head(self._mem, self.addr, node.addr)

    def add_tail(self, node):
        list_add_tail(self._mem, self.addr, node.addr)

    def _result(self, addr, promote):
        node = self._node(addr)
        return node.promote_type() if promote else node

    def rem_head(self, promote=False):
        addr = list_rem_head(self._mem, self.addr)
        if addr == 0:
            return None
        return self._result(addr, promote)

    def rem_tail(self, promote=False):
        mem = self._mem
        addr = mem.r32(self.addr + _TAIL_PRED)
        if addr == 0 or mem.r32(addr + PRED) == 0:
            return None
        remove_node(mem, addr)
        return self._result(addr, promote)

    def get_head(self, promote=False):
        addr = list_first(self._mem, self.addr)
        if addr == 0:
            return None
        return self._result(addr, promote)

    def get_tail(self, promote=False):
        mem = self._mem
        addr = mem.r32(self.addr + _TAIL_PRED)
        if addr == 0 or mem.r32(addr + PRED) == 0:
            return None
        return self._result(addr, promote)

    def insert(self, node, pred):
        if pred is not None and pred.addr != self.addr + _HEAD:
            mem = self._mem
            pred_succ = mem.r32(pred.addr + SUCC)
            if pred_succ:
                # normal node
                addr = node.addr
                mem.w32(addr + SUCC, pred_succ)
                mem.w32(addr + PRED, pred.addr)
                mem.w32(pred_succ + PRED, addr)
                mem.w32(pred.addr + SUCC, addr)
            else:
                # last node
                self.add_tail(node)
        else:
            # first node
            self.add_head(node)


@AmigaClassDef
class MinList(MinListStruct, ListBase):
    _node_type = MinNode

    def __str__(self):
        return "[MinList:@%06x,h=%06x,t=%06x,tp=%06x]" % (
            self.addr,
            self.head.aptr,
            self.tail.aptr,
            self.tail_pred.aptr,
        )

    def new(self):
        self.head.ref = self._tail
        self.tail.ref = None
        self.tail_pred.ref = self._head


@AmigaClassDef
class List(ListStruct, ListBase):
    _node_type = Node

    def __iter__(self):
        """default Python iter is returning Nodes and does not promote"""
        return ListIter(self, promote=False)

    def iter(self, **kw_args):
        """alternative iterator that allows to pass paramters"""
        return ListIter(self, **kw_args)

    def __str__(self):
        return "[List:@%06x,h=%06x,t=%06x,tp=%06x,%s]" % (
            self.addr,
            self.head.aptr,
            self.tail.aptr,
            self.tail_pred.aptr,
            self.type,
        )

    def get_path(self, path, promote=False):
        # allow to search list via arg
        if len(path) == 0:
            if promote:
                return self.promote_type()
            else:
                return self
        # arg?
        arg = self._get_path_arg(path)
        if arg:
            sub_obj = self.find_name(arg)
            if sub_obj:
                sub_path = self._skip_path_arg(path, arg)
                return sub_obj.get_path(sub_path)

    # ----- list ops -----

    def new(self, lt):
        self.type.val = lt
        self.head.ref = self._tail
        self.tail.ref = None
        self.tail_pred.ref = self._head

    def enqueue(self, node):
        pred = None
        pri = node.pri.val
        for ln in self:
            ln_pri = ln.pri.val
            if ln_pri < pri:
                self.insert(node, pred)
                return
            pred = ln
        self.add_tail(node)

    def find_names(self, name, promote=False):
        """this method is a generator delivering all matches"""
        for node in ListIter(self, None):
            node_name = node.name.str
            if node_name == name:
                if promote:
                    yield node.promote_type()
                else:
                    yield node

    def find_name(self, name, promote=False):
        """this method is a function returning the first match"""
        for node in ListIter(self, None):
            node_name = node.name.str
            if node_name == name:
                if promote:
                    return node.promote_type()
                else:
                    return node
