from amitools.vamos.libstructs import MessageStruct, MsgPortStruct, NodeType
from amitools.vamos.astructs import AmigaClassDef


@AmigaClassDef
class MsgPort(MsgPortStruct):
    def new_port(self, pri=0, flags=0, sig_bit=0, sig_task=0, nt=NodeType.NT_MSGPORT):
        self.pri.val = pri
        self.type.val = nt
        self.flags.val = flags
        self.sig_bit.val = sig_bit
        self.sig_task.setup(sig_task)
        self.msg_list.new_list(NodeType.NT_MESSAGE)


@AmigaClassDef
class Message(MessageStruct):
    def new_msg(self, pri=0, reply_port=0, length=0, nt=NodeType.NT_MESSAGE):
        self.pri.val = pri
        self.type.val = nt
        self.reply_port.setup(reply_port)
        self.length.val = length
