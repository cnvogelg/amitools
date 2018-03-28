from amitools.vamos.astructs import NodeDef
from amitools.vamos.mem import AccessStruct
from .nodetype import NodeType


class Node(object):
  """wrap an Exec Node in memory an allow to operate on its values.
     also suppors MinNode by simply not using any ops on type, pri, and name"""

  def __init__(self, mem, addr, min_node=False):
    self.mem = mem
    self.addr = addr
    self.access = AccessStruct(mem, NodeDef, addr)
    self.min_node = min_node

  def __str__(self):
    if self.min_node:
      return "[MinNode:@%06x,p=%06x,s=%06x]" % \
          (self.addr, self.get_pred(), self.get_succ())
    else:
      return "[Node:@%06x,p=%06x,s=%06x,%s,%d,'%s']" % \
          (self.addr, self.get_pred(), self.get_succ(),
           NodeType.to_str(self.get_type()),
           self.get_pri(), self.get_name())

  def __eq__(self, other):
    return self.mem == other.mem and self.addr == other.addr

  def get_size(self):
    return self.access.get_size()

  def get_succ(self):
    return self.access.r_s('ln_Succ')

  def get_pred(self):
    return self.access.r_s('ln_Pred')

  def get_succ_node(self):
    return Node(self.mem, self.get_succ())

  def get_pred_node(self):
    return Node(self.mem, self.get_pred())

  def get_type(self):
    return self.access.r_s('ln_Type')

  def get_pri(self):
    if self.min_node:
      raise RuntimeError("min_node has no pri!")
    return self.access.r_s('ln_Pri')

  def get_name(self):
    if self.min_node:
      raise RuntimeError("min_node has no name!")
    name_addr = self.access.r_s('ln_Name')
    return self.mem.r_cstr(name_addr)

  def get_name_addr(self):
    if self.min_node:
      raise RuntimeError("min_node has no pri!")
    return self.access.r_s('ln_Name')

  def set_succ(self, addr):
    self.access.w_s('ln_Succ', addr)

  def set_pred(self, addr):
    self.access.w_s('ln_Pred', addr)

  def set_type(self, nt):
    self.access.w_s('ln_Type', nt)

  def set_pri(self, pri):
    if self.min_node:
      raise RuntimeError("min_node has no pri!")
    self.access.w_s('ln_Pri', pri)

  def set_name_addr(self, addr):
    if self.min_node:
      raise RuntimeError("min_node has no name!")
    self.access.w_s('ln_Name', addr)

  def setup(self, succ, pred, nt, pri, name_addr):
    self.access.w_s('ln_Succ', succ)
    self.access.w_s('ln_Pred', pred)
    self.access.w_s('ln_Type', nt)
    self.access.w_s('ln_Pri', pri)
    self.access.w_s('ln_Name', name_addr)

  def min_setup(self, succ, pred):
    self.access.w_s('ln_Succ', succ)
    self.access.w_s('ln_Pred', pred)

  def get_node(self):
    return self.access.r_all()

  def set_node(self, node):
    self.access.w_all(node)

  # ----- node ops -----

  def remove(self, clear=True):
    succ = self.get_succ()
    pred = self.get_pred()
    if succ == 0 or pred == 0:
      raise ValueError("remove node without succ/pred!")
    sn = Node(self.mem, succ)
    pn = Node(self.mem, pred)
    sn.set_pred(pred)
    pn.set_succ(succ)
    if clear:
      self.set_succ(0)
      self.set_pred(0)

  def find_name(self, name):
    """find name after this node"""
    if self.min_node:
      raise RuntimeError("min_node has no name!")
    succ = self.get_succ()
    if succ == 0:
      return None
    succ_node = Node(self.mem, succ)
    succ_name = succ_node.get_name()
    if succ_name == name:
      return succ_node
    return succ_node.find_name(name)
