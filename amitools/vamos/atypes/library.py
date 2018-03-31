from amitools.vamos.astructs import LibraryStruct
from .atype import AmigaType
from .atypedef import AmigaTypeDef
from .node import NodeType
from .enum import EnumType


@EnumType
class LibFlags(object):
  LIBF_SUMMING = (1 << 0)
  LIBF_CHANGED = (1 << 1)
  LIBF_SUMUSED = (1 << 2)
  LIBF_DELEXP = (1 << 3)


@AmigaTypeDef(LibraryStruct, wrap={'Flags': LibFlags})
class Library(AmigaType):

  def set_name(self, val):
    self.get_node().set_name(val)

  def get_name(self, ptr=False):
    return self.get_node().get_name(ptr)
