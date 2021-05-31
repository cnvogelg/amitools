import pytest
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.libtypes import Node, MinNode
from amitools.vamos.libstructs import NodeStruct, MinNodeStruct, NodeType


def libtypes_node_type_to_str_test():
    assert NodeType.to_str(NodeType.NT_UNKNOWN) == "NT_UNKNOWN"
    with pytest.raises(ValueError):
        NodeType.to_str(-1)


def libtypes_node_type_from_str_test():
    assert NodeType.from_str("NT_INTERRUPT") == NodeType.NT_INTERRUPT
    with pytest.raises(ValueError):
        NodeType.from_str("bla")


def libtypes_node_base_test():
    mem = MockMemory()
    text = "hello, world!"
    mem.w_cstr(12, text)
    node = Node(mem, 0x42)
    # set node
    node.succ.aptr = 1234
    node.pred.aptr = 5678
    node.type.val = NodeType.NT_LIBRARY
    node.pri.val = -3
    node.name.aptr = 12
    # check node
    assert node.succ.aptr == 1234
    assert node.pred.aptr == 5678
    assert node.type.val == NodeType.NT_LIBRARY
    assert node.pri.val == -3
    assert node.name.aptr == 12
    assert node.name.str == text


def libtypes_node_setup_test():
    mem = MockMemory()
    text = "hello, world!"
    mem.w_cstr(12, text)
    node = Node(
        mem, 0x42, succ=1234, pred=5678, type=NodeType.NT_DEVICE, pri=-5, name=12
    )
    # check node
    assert node.succ.aptr == 1234
    assert node.pred.aptr == 5678
    assert node.type.val == NodeType.NT_DEVICE
    assert node.pri.val == -5
    assert node.name.aptr == 12
    assert node.name.str == text
    node.type.val = NodeType.NT_DEVICE


def libtypes_node_setup_min_test():
    mem = MockMemory()
    node = MinNode(mem, 0x42, succ=1234, pred=5678)
    # check node
    assert node.succ.aptr == 1234
    assert node.pred.aptr == 5678


def libtypes_node_str_test():
    mem = MockMemory()
    text = "hello, world!"
    mem.w_cstr(12, text)
    node = Node(
        mem, 0x42, succ=0x1234, pred=0x5678, type=NodeType.NT_DEVICE, pri=-5, name=12
    )
    assert str(node) == "[Node:@000042,p=005678,s=001234,NT_DEVICE,-5,'hello, world!']"


def libtypes_node_str_min_test():
    mem = MockMemory()
    min_node = MinNode(mem, 0x80, succ=0x1234, pred=0x5678)
    assert str(min_node) == "[MinNode:@000080,p=005678,s=001234]"


def libtypes_node_remove_test():
    mem = MockMemory()
    text = "hello, world!"
    mem.w_cstr(12, text)
    node = Node(
        mem, 0x80, succ=0x60, pred=0x100, type=NodeType.NT_DEVICE, pri=-5, name=12
    )
    node.remove()


def libtypes_node_remove_min_test():
    mem = MockMemory()
    min_node = MinNode(mem, 0x80, succ=0x60, pred=0x100)
    min_node.remove()


def libtypes_node_alloc_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    node = Node.alloc(alloc)
    assert node.get_size() == NodeStruct.get_size()
    node.free()
    assert alloc.is_all_free()


def libtypes_node_alloc_name_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    node = Node.alloc(alloc, name="foobar")
    assert node.get_size() == NodeStruct.get_size()
    assert node.name.str == "foobar"
    node.free()
    assert alloc.is_all_free()


def libtypes_node_alloc_min_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    node = MinNode.alloc(alloc)
    assert node.get_size() == MinNodeStruct.get_size()
    node.free()
    assert alloc.is_all_free()
