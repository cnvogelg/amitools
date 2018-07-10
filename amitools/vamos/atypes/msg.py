from amitools.vamos.astructs import MessageStruct, MsgPortStruct
from .atype import AmigaType
from .atypedef import AmigaTypeDef
from .enum import EnumType


@EnumType
class MsgPortFlags(object):
  PA_SIGNAL = 0
  PA_SOFINT = 1
  PA_IGNORE = 2


@AmigaTypeDef(MsgPortStruct, wrap={'mp_Flags': MsgPortFlags})
class MsgPort(AmigaType):
  pass


@AmigaTypeDef(MessageStruct)
class Message(AmigaType):
  pass
