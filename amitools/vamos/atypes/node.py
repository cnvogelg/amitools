from amitools.vamos.astructs import NodeDef
from .atype import AmigaType
from .enum import EnumType


@EnumType
class NodeType(object):
  """manage valid node type constants and conversions"""
  NT_UNKNOWN = 0
  NT_TASK = 1
  NT_INTERRUPT = 2
  NT_DEVICE = 3
  NT_MSGPORT = 4
  NT_MESSAGE = 5
  NT_FREEMSG = 6
  NT_REPLYMSG = 7
  NT_RESOURCE = 8
  NT_LIBRARY = 9
  NT_MEMORY = 10
  NT_SOFTINT = 11
  NT_FONT = 12
  NT_PROCESS = 13
  NT_SEMAPHORE = 14
  NT_SIGNALSEM = 15
  NT_BOOTNODE = 16
  NT_KICKMEM = 17
  NT_GRAPHICS = 18
  NT_DEATHMESSAGE = 19

  NT_USER = 254
  NT_EXTENDED = 255


@AmigaType(NodeDef, wrap={'type': (NodeType, long)})
class Node(object):
  """wrap an Exec Node in memory an allow to operate on its values.
     also suppors MinNode by simply not using any ops on type, pri, and name"""

  def __init__(self, min_node=False):
    self.min_node = min_node

  def __str__(self):
    if self.min_node:
      return "[MinNode:@%06x,p=%06x,s=%06x]" % \
          (self.addr, self.get_pred(), self.get_succ())
    else:
      return "[Node:@%06x,p=%06x,s=%06x,%s,%d,'%s']" % \
          (self.addr, self.get_pred(), self.get_succ(),
           self.get_type(), self.get_pri(), self.get_name())

  def __eq__(self, other):
    return self.mem == other.mem and self.addr == other.addr

  def get_succ_node(self):
    return Node(self.mem, self.get_succ())

  def get_pred_node(self):
    return Node(self.mem, self.get_pred())

  def setup(self, succ, pred, nt, pri, name_addr):
    self.set_succ(succ)
    self.set_pred(pred)
    self.set_type(nt)
    self.set_pri(pri)
    self.set_name_addr(name_addr)

  def min_setup(self, succ, pred):
    self.set_succ(succ)
    self.set_pred(pred)

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
