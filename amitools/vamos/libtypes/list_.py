from amitools.vamos.libstructs import ListStruct, MinListStruct
from amitools.vamos.astructs import AmigaClassDef
from .node import Node, MinNode


class ListIter(object):
    def __init__(self, alist, start_node=None, promote=False):
        self.alist = alist
        self.mem = self.alist._mem
        self.promote = promote
        if start_node is None:
            self.node = alist._head.succ.ref
        else:
            self.node = start_node

    def __iter__(self):
        return self

    def __next__(self):
        succ = self.node.succ.ref
        if succ is None:
            raise StopIteration()
        res = self.node
        self.node = succ
        if self.promote:
            return res.promote_type()
        else:
            return res


class ListBase:
    def __iter__(self):
        return ListIter(self)

    def __len__(self):
        l = 0
        node = self._head.succ.ref
        while True:
            node = node.succ.ref
            if node is None:
                break
            l += 1
        return l

    def is_empty(self):
        node = self._head.succ.ref
        return node.succ.ref is None

    def to_list(self, promote=False):
        return [a for a in ListIter(self, promote=promote)]

    def iter_at(self, node, promote=False):
        return ListIter(self, start_node=node, promote=promote)

    def add_head(self, node):
        n = self._head.succ.ref
        node.pred.ref = self._head
        node.succ.ref = n
        self._head.succ.ref = node
        n.pred.ref = node

    def add_tail(self, node):
        tp = self.tail_pred.ref
        node.succ.ref = self._tail
        self._tail.pred.ref = node
        node.pred.ref = tp
        tp.succ.ref = node

    def rem_head(self, promote=False):
        node = self._head.succ.ref
        if node.succ.ref is None:
            return None
        node.remove()
        if promote:
            return node.promote_type()
        else:
            return node

    def rem_tail(self, promote=False):
        node = self.tail_pred.ref
        if node.pred.ref is None:
            return None
        node.remove()
        if promote:
            return node.promote_type()
        else:
            return node

    def get_head(self, promote=False):
        node = self._head.succ.ref
        if node.succ.ref is None:
            return None
        if promote:
            return node.promote_type()
        else:
            return node

    def get_tail(self, promote=False):
        node = self.tail_pred.ref
        if node.pred.ref is None:
            return None
        if promote:
            return node.promote_type()
        else:
            return node

    def insert(self, node, pred):
        if pred is not None and pred != self._head:
            pred_succ = pred.succ.ref
            if pred_succ:
                # normal node
                node.succ.ref = pred_succ
                node.pred.ref = pred
                pred_succ.pred.ref = node
                pred.succ.ref = node
            else:
                # last node
                self.add_tail(node)
        else:
            # first node
            self.add_head(node)


@AmigaClassDef
class MinList(MinListStruct, ListBase):
    def __init__(self, mem, addr, **kwargs):
        super().__init__(mem, addr, **kwargs)
        self._head = MinNode(mem, self.addr)
        self._tail = MinNode(mem, self.addr + 4)

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
    def __init__(self, mem, addr, **kwargs):
        super().__init__(mem, addr, **kwargs)
        self._head = Node(mem, self.addr)
        self._tail = Node(mem, self.addr + 4)

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
