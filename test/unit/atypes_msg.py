import pytest
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.atypes import MsgPort, Message, MsgPortFlags, NodeType


def atypes_msg_msgport_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    # alloc msg port
    mp1 = MsgPort.alloc(alloc)
    assert mp1.name == 0
    mp1.setup(pri=-5, flags=MsgPortFlags.PA_SOFTINT, sig_bit=5)
    assert mp1.node.pri == -5
    assert mp1.node.type == NodeType.NT_MSGPORT
    assert mp1.flags == MsgPortFlags.PA_SOFTINT
    assert mp1.sig_bit == 5
    assert mp1.sig_task == 0
    assert len(mp1.msg_list) == 0
    # with name
    mp2 = MsgPort.alloc(alloc, "bla")
    assert mp2.get_name() == "bla"
    # free
    mp1.free()
    mp2.free()
    assert alloc.is_all_free()


def atypes_msg_msg_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    # alloc msg
    msg = Message.alloc(alloc)
    assert msg.name == 0
    msg.setup(pri=-7, length=10)
    assert msg.node.pri == -7
    assert msg.node.type == NodeType.NT_MESSAGE
    assert msg.length == 10
    # with name
    msg2 = Message.alloc(alloc, "bla")
    assert msg2.name == "bla"
    # free
    msg.free()
    msg2.free()
    assert alloc.is_all_free()
