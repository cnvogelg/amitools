import pytest
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.libtypes import MsgPort, Message
from amitools.vamos.libstructs import MsgPortFlags, NodeType


def libtypes_msg_msgport_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    # alloc msg port
    mp1 = MsgPort.alloc(alloc)
    assert mp1.name.aptr == 0
    mp1.new_port(pri=-5, flags=MsgPortFlags.PA_SOFTINT, sig_bit=5)
    assert mp1.node.pri.val == -5
    assert mp1.node.type.val == NodeType.NT_MSGPORT
    assert mp1.flags.val == MsgPortFlags.PA_SOFTINT
    assert mp1.sig_bit.val == 5
    assert mp1.sig_task.aptr == 0
    assert len(mp1.msg_list) == 0
    # with name
    mp2 = MsgPort.alloc(alloc, name="bla")
    assert mp2.name.str == "bla"
    # free
    mp1.free()
    mp2.free()
    assert alloc.is_all_free()


def libtypes_msg_msg_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    # alloc msg
    msg = Message.alloc(alloc)
    assert msg.name.aptr == 0
    msg.new_msg(pri=-7, length=10)
    assert msg.pri.val == -7
    assert msg.type.val == NodeType.NT_MESSAGE
    assert msg.length.val == 10
    # with name
    msg2 = Message.alloc(alloc, name="bla")
    assert msg2.name.str == "bla"
    # free
    msg.free()
    msg2.free()
    assert alloc.is_all_free()
