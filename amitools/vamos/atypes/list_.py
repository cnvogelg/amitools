from amitools.vamos.astructs import ListStruct, MinListStruct
from .node import Node, NodeType
from .atype import AmigaType
from .atypedef import AmigaTypeDef


class ListIter(object):

  def __init__(self, alist, start_node=None):
    self.alist = alist
    self.mem = self.alist.mem
    if start_node is None:
      self.node = alist.head.get_succ()
    else:
      self.node = start_node

  def __iter__(self):
    return self

  def next(self):
    succ = self.node.get_succ()
    if succ is None:
      raise StopIteration()
    res = self.node
    self.node = succ
    return res


@AmigaTypeDef(ListStruct, wrap={'type': NodeType})
class List(AmigaType):

  def __init__(self, mem, addr, min_list=False):
    AmigaType.__init__(self, mem, addr)
    self.head = Node(mem, self.addr, min_node=True)
    self.tail = Node(mem, self.addr + 4, min_node=True)
    self.min_list = min_list

  def __str__(self):
    if self.min_list:
      return "[MinList:@%06x,h=%06x,t=%06x,tp=%06x]" % \
          (self.addr, self.get_head(True),
           self.get_tail(True), self.get_tail_pred(True))
    else:
      return "[List:@%06x,h=%06x,t=%06x,tp=%06x,%s]" % \
          (self.addr, self.get_head(True),
           self.get_tail(True), self.get_tail_pred(True),
           self.get_type())

  @classmethod
  def alloc_min(cls, alloc, tag=None, size=None):
    if size is None:
      size = MinListStruct.get_size()
    return cls.alloc(alloc, tag, size)

  # ----- list ops -----

  def __iter__(self):
    return ListIter(self)

  def __len__(self):
    l = 0
    node = self.head.get_succ()
    while True:
      node = node.get_succ()
      if node is None:
        break
      l += 1
    return l

  def iter_at(self, node):
    return ListIter(self, node)

  def new_list(self, lt):
    self.set_type(lt)
    self.set_head(self.tail)
    self.set_tail(0)
    self.set_tail_pred(self.head)

  def new_min_list(self):
    self.set_head(self.tail)
    self.set_tail(0)
    self.set_tail_pred(self.head)

  def add_head(self, node):
    n = self.head.get_succ()
    node.set_pred(self.head)
    node.set_succ(n)
    self.head.set_succ(node)
    n.set_pred(node)

  def add_tail(self, node):
    tp = self.get_tail_pred()
    node.set_succ(self.tail)
    self.tail.set_pred(node)
    node.set_pred(tp)
    tp.set_succ(node)

  def rem_head(self):
    node = self.head.get_succ()
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
    if pred is not None and pred != self.head:
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

  def enqueue(self, node):
    if self.min_list:
      raise RuntimeError("do not enqueue on MinList!")
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
    if self.min_list:
      raise RuntimeError("do not find_name on MinList!")
    for node in self:
      node_name = node.get_name()
      if node_name == name:
        yield node

  def find_name(self, name):
    """this method is a generator delivering all matches"""
    if self.min_list:
      raise RuntimeError("do not find_name on MinList!")
    for node in self:
      node_name = node.get_name()
      if node_name == name:
        return node
