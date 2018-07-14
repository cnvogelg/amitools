from amitools.vamos.astructs import NodeStruct, MinNodeStruct
from .atype import AmigaType, AmigaTypeWithName
from .atypedef import AmigaTypeDef
from .enum import EnumType
from .cstring import CString


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


# common funcs for nodes

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


funcs = {
    'remove': remove
}


@AmigaTypeDef(MinNodeStruct, funcs=funcs)
class MinNode(AmigaType):
  """wrap an Exec MinNode in memory an allow to operate on its values.
  """

  def __str__(self):
    return "[MinNode:@%06x,p=%06x,s=%06x]" % \
        (self.addr, self.get_pred(True), self.get_succ(True))

  def setup(self, succ, pred):
    self.set_succ(succ)
    self.set_pred(pred)


@AmigaTypeDef(NodeStruct, wrap={'type': NodeType}, funcs=funcs)
class Node(AmigaTypeWithName):
  """wrap an Exec Node in memory an allow to operate on its values.
  """

  def __str__(self):
    return "[Node:@%06x,p=%06x,s=%06x,%s,%d,'%s']" % \
        (self.addr, self.get_pred(True), self.get_succ(True),
         self.get_type(), self.get_pri(), self.get_name())

  def setup(self, succ, pred, nt, pri, name=None):
    self.set_succ(succ)
    self.set_pred(pred)
    self.set_type(nt)
    self.set_pri(pri)
    if name:
      self.set_name(name)

  # ----- node ops -----

  def find_name(self, name):
    """find name after this node"""
    succ = self.get_succ()
    if succ is None:
      return None
    succ_name = succ.get_name()
    if succ_name == name:
      return succ
    return succ.find_name(name)
