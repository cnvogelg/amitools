from amitools.vamos.astructs import MessageStruct, MsgPortStruct
from .atype import AmigaTypeWithName
from .atypedef import AmigaTypeDef
from .enum import EnumType
from .node import NodeType


@EnumType
class MsgPortFlags(object):
  PA_SIGNAL = 0
  PA_SOFTINT = 1
  PA_IGNORE = 2


@AmigaTypeDef(MsgPortStruct, wrap={'Flags': MsgPortFlags})
class MsgPort(AmigaTypeWithName):

  def set_name(self, val):
    self.get_node().set_name(val)

  def get_name(self, ptr=False):
    return self.get_node().get_name(ptr)

  def setup(self, pri=0, flags=0, sig_bit=0, sig_task=0,
            nt=NodeType.NT_MSGPORT):
    self.node.set_pri(pri)
    self.node.set_type(nt)
    self.set_flags(flags)
    self.set_sig_bit(sig_bit)
    self.set_sig_task(sig_task)
    self.msg_list.new_list(NodeType.NT_MESSAGE)


@AmigaTypeDef(MessageStruct)
class Message(AmigaTypeWithName):

  def set_name(self, val):
    self.get_node().set_name(val)

  def get_name(self, ptr=False):
    return self.get_node().get_name(ptr)

  def setup(self, pri=0, reply_port=0, length=0,
            nt=NodeType.NT_MESSAGE):
    self.node.set_pri(pri)
    self.node.set_type(nt)
    self.set_reply_port(reply_port)
    self.set_length(length)
