from amitools.vamos.lib.lexec.ExecStruct import ListDef
from amitools.vamos.mem import AccessStruct
from .node import Node
from .nodetype import NodeType


class ListIter(object):

  def __init__(self, alist, start_node=None):
    self.alist = alist
    self.mem = self.alist.mem
    if start_node is None:
      self.node = Node(self.mem, alist.get_head())
    else:
      self.node = start_node

  def __iter__(self):
    return self

  def next(self):
    succ = self.node.get_succ()
    if succ == 0:
      raise StopIteration()
    res = self.node
    self.node = Node(self.mem, succ)
    return res


class List(object):

  def __init__(self, mem, addr, min_list=False):
    self.mem = mem
    self.head_addr = addr
    self.tail_addr = addr + 4
    self.min_list = min_list
    self.access = AccessStruct(mem, ListDef, addr)

  def __str__(self):
    if self.min_list:
      return "[MinList:@%06x,h=%06x,t=%06x,tp=%06x]" % \
          (self.head_addr, self.get_head(),
           self.get_tail(), self.get_tail_pred())
    else:
      return "[List:@%06x,h=%06x,t=%06x,tp=%06x,%s]" % \
          (self.head_addr, self.get_head(),
           self.get_tail(), self.get_tail_pred(),
           NodeType.to_str(self.get_type()))

  def __eq__(self, other):
    return self.mem == other.mem and self.head_addr == other.head_addr

  def set_head(self, head):
    self.access.w_s('lh_Head', head)

  def get_head(self):
    return self.access.r_s('lh_Head')

  def set_tail(self, tail):
    self.access.w_s('lh_Tail', tail)

  def get_tail(self):
    return self.access.r_s('lh_Tail')

  def set_tail_pred(self, tp):
    self.access.w_s('lh_TailPred', tp)

  def get_tail_pred(self):
    return self.access.r_s('lh_TailPred')

  def set_type(self, lt):
    self.access.w_s('lh_Type', lt)

  def get_type(self):
    return self.access.r_s('lh_Type')

  # ----- list ops -----

  def __iter__(self):
    return ListIter(self)

  def __len__(self):
    node = Node(self.mem, self.get_head())
    l = 0
    succ = node.get_succ()
    while succ != 0:
      l += 1
      node = Node(self.mem, succ)
      succ = node.get_succ()
    return l

  def iter_at(self, node):
    return ListIter(self, node)

  def new_list(self, lt):
    self.set_type(lt)
    self.set_head(self.tail_addr)
    self.set_tail(0)
    self.set_tail_pred(self.head_addr)

  def new_min_list(self):
    self.set_head(self.tail_addr)
    self.set_tail(0)
    self.set_tail_pred(self.head_addr)

  def add_head(self, node):
    na = node.addr
    node.set_pred(self.head_addr)
    head = self.get_head()
    node.set_succ(head)
    n = Node(self.mem, head)
    n.set_pred(na)
    self.set_head(na)

  def add_tail(self, node):
    na = node.addr
    node.set_succ(self.tail_addr)
    tp = self.get_tail_pred()
    node.set_pred(tp)
    n = Node(self.mem, tp)
    n.set_succ(na)
    self.set_tail_pred(na)

  def rem_head(self):
    head = self.get_head()
    hn = Node(self.mem, head)
    succ = hn.get_succ()
    if succ == 0:
      return None
    hn.remove()
    return hn

  def rem_tail(self):
    tp = self.get_tail_pred()
    tn = Node(self.mem, tp)
    pred = tn.get_pred()
    if pred == 0:
      return None
    tn.remove()
    return tn

  def insert(self, node, pred):
    if pred is not None and pred.addr != 0 and pred.addr != self.head_addr:
      pred_succ = pred.get_succ()
      if pred_succ != 0:
        # normal node
        node.set_succ(pred_succ)
        node.set_pred(pred.addr)
        pred_succ_node = Node(self.mem, pred_succ)
        pred_succ_node.set_pred(node.addr)
        pred.set_succ(node.addr)
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
