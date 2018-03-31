from amitools.vamos.astructs import NodeStruct, MinNodeStruct
from .atype import AmigaType
from .atypedef import AmigaTypeDef
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


@AmigaTypeDef(NodeStruct, wrap={'type': NodeType})
class Node(AmigaType):
  """wrap an Exec Node in memory an allow to operate on its values.
     also suppors MinNode by simply not using any ops on type, pri, and name"""

  def __init__(self, mem, addr, min_node=False):
    AmigaType.__init__(self, mem, addr)
    self.min_node = min_node

  def __str__(self):
    if self.min_node:
      return "[MinNode:@%06x,p=%06x,s=%06x]" % \
          (self.addr, self.get_pred(True), self.get_succ(True))
    else:
      return "[Node:@%06x,p=%06x,s=%06x,%s,%d,'%s']" % \
          (self.addr, self.get_pred(True), self.get_succ(True),
           self.get_type(), self.get_pri(), self.get_name())

  @classmethod
  def alloc_min(cls, mem, alloc, tag=None, size=None):
    if size is None:
      size = MinNodeStruct.get_size()
    return cls.alloc(mem, alloc, tag, size)

  def setup(self, succ, pred, nt, pri, name):
    self.set_succ(succ)
    self.set_pred(pred)
    self.set_type(nt)
    self.set_pri(pri)
    self.set_name(name)

  def setup_min(self, succ, pred):
    self.set_succ(succ)
    self.set_pred(pred)

  # ----- node ops -----

  def remove(self, clear=True):
    succ = self.get_succ()
    pred = self.get_pred()
    if succ is None or pred is None:
      raise ValueError("remove node without succ/pred!")
    succ.set_pred(pred)
    pred.set_succ(succ)
    if clear:
      self.set_succ(None)
      self.set_pred(None)

  def find_name(self, name):
    """find name after this node"""
    if self.min_node:
      raise RuntimeError("min_node has no name!")
    succ = self.get_succ()
    if succ is None:
      return None
    succ_name = succ.get_name()
    if succ_name == name:
      return succ
    return succ.find_name(name)
