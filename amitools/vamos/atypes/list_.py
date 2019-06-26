from amitools.vamos.astructs import ListStruct, MinListStruct
from .node import Node, NodeType, MinNode
from .atype import AmigaType
from .atypedef import AmigaTypeDef


class ListIter(object):

  def __init__(self, alist, start_node=None):
    self.alist = alist
    self.mem = self.alist._mem
    if start_node is None:
      self.node = alist._head.get_succ()
    else:
      self.node = start_node

  def __iter__(self):
    return self

  def __next__(self):
    succ = self.node.get_succ()
    if succ is None:
      raise StopIteration()
    res = self.node
    self.node = succ
    return res


# common list funcs

def iter_func(self):
  return ListIter(self)


def len_func(self):
  l = 0
  node = self._head.get_succ()
  while True:
    node = node.get_succ()
    if node is None:
      break
    l += 1
  return l


def iter_at(self, node):
  return ListIter(self, node)


def add_head(self, node):
  n = self._head.get_succ()
  node.set_pred(self._head)
  node.set_succ(n)
  self._head.set_succ(node)
  n.set_pred(node)


def add_tail(self, node):
  tp = self.get_tail_pred()
  node.set_succ(self._tail)
  self._tail.set_pred(node)
  node.set_pred(tp)
  tp.set_succ(node)


def rem_head(self):
  node = self._head.get_succ()
  if node is None:
    return None
  node.remove()
  return node


def rem_tail(self):
  node = self.get_tail_pred()
  if node is None:
    return None
  node.remove()
  return node


def insert(self, node, pred):
  if pred is not None and pred != self._head:
    pred_succ = pred.get_succ()
    if pred_succ:
      # normal node
      node.set_succ(pred_succ)
      node.set_pred(pred)
      pred_succ.set_pred(node)
      pred.set_succ(node)
    else:
      # last node
      self.add_tail(node)
  else:
    # first node
    self.add_head(node)


funcs = {
    '__iter__': iter_func,
    '__len__': len_func,
    'iter_at': iter_at,
    'add_head': add_head,
    'add_tail': add_tail,
    'rem_head': rem_head,
    'rem_tail': rem_tail,
    'insert': insert
}


@AmigaTypeDef(MinListStruct, funcs=funcs)
class MinList(AmigaType):

  def __init__(self, mem, addr):
    AmigaType.__init__(self, mem, addr)
    self._head = MinNode(mem, self.addr)
    self._tail = MinNode(mem, self.addr + 4)

  def __str__(self):
    return "[MinList:@%06x,h=%06x,t=%06x,tp=%06x]" % \
        (self.addr, self.get_head(True),
         self.get_tail(True), self.get_tail_pred(True))

  def new_list(self):
    self.set_head(self._tail)
    self.set_tail(0)
    self.set_tail_pred(self._head)


@AmigaTypeDef(ListStruct, wrap={'type': NodeType}, funcs=funcs)
class List(AmigaType):

  def __init__(self, mem, addr):
    AmigaType.__init__(self, mem, addr)
    self._head = Node(mem, self.addr)
    self._tail = Node(mem, self.addr + 4)

  def __str__(self):
    return "[List:@%06x,h=%06x,t=%06x,tp=%06x,%s]" % \
        (self.addr, self.get_head(True),
         self.get_tail(True), self.get_tail_pred(True),
         self.get_type())

  # ----- list ops -----

  def new_list(self, lt):
    self.set_type(lt)
    self.set_head(self._tail)
    self.set_tail(0)
    self.set_tail_pred(self._head)

  def enqueue(self, node):
    pred = None
    pri = node.get_pri()
    for ln in self:
      ln_pri = ln.get_pri()
      if ln_pri < pri:
        self.insert(node, pred)
        return
      pred = ln
    self.add_tail(node)

  def find_names(self, name):
    """this method is a generator delivering all matches"""
    for node in self:
      node_name = node.get_name()
      if node_name == name:
        yield node

  def find_name(self, name):
    """this method is a function returning the first match"""
    for node in self:
      node_name = node.get_name()
      if node_name == name:
        return node
