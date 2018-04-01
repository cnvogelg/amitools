import pytest
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.atypes import Node, NodeType
from amitools.vamos.astructs import NodeStruct, MinNodeStruct


def atypes_node_type_to_str_test():
  assert NodeType.to_str(NodeType.NT_UNKNOWN) == 'NT_UNKNOWN'
  with pytest.raises(ValueError):
    NodeType.to_str(-1)


def atypes_node_type_from_str_test():
  assert NodeType.from_str('NT_INTERRUPT') == NodeType.NT_INTERRUPT
  with pytest.raises(ValueError):
    NodeType.from_str('bla')


def atypes_node_base_test():
  mem = MockMemory()
  text = 'hello, world!'
  mem.w_cstr(12, text)
  node = Node(mem, 0x42)
  # set node
  node.set_succ(1234)
  node.set_pred(5678)
  node.set_type(NodeType.NT_LIBRARY)
  node.set_pri(-3)
  node.set_name(12)
  # check node
  assert node.get_succ() == 1234
  assert node.get_pred() == 5678
  assert int(node.get_type()) == NodeType.NT_LIBRARY
  assert node.get_type() == NodeType(NodeType.NT_LIBRARY)
  assert node.get_pri() == -3
  assert node.get_name(True) == 12
  assert node.get_name() == text


def atypes_node_setup_test():
  mem = MockMemory()
  text = 'hello, world!'
  mem.w_cstr(12, text)
  node = Node(mem, 0x42)
  node.setup(1234, 5678, NodeType.NT_DEVICE, -5, 12)
  # check node
  assert node.get_succ() == 1234
  assert node.get_pred() == 5678
  assert int(node.get_type()) == NodeType.NT_DEVICE
  assert node.get_pri() == -5
  assert node.get_name(True) == 12
  assert node.get_name() == text
  node.set_type(NodeType(NodeType.NT_DEVICE))


def atypes_node_setup_min_test():
  mem = MockMemory()
  node = Node(mem, 0x42)
  node.setup_min(1234, 5678)
  # check node
  assert node.get_succ() == 1234
  assert node.get_pred() == 5678


def atypes_node_str_test():
  mem = MockMemory()
  text = 'hello, world!'
  mem.w_cstr(12, text)
  node = Node(mem, 0x42)
  node.setup(0x1234, 0x5678, NodeType.NT_DEVICE, -5, 12)
  assert str(node) == \
      "[Node:@000042,p=005678,s=001234,NT_DEVICE,-5,'hello, world!']"
  min_node = Node(mem, 0x80, True)
  min_node.setup_min(0x1234, 0x5678)
  assert str(min_node) == "[MinNode:@000080,p=005678,s=001234]"


def atypes_node_alloc_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  node = Node.alloc(alloc)
  assert node.get_size() == NodeStruct.get_size()
  node.free()
  # min
  node = Node.alloc_min(alloc)
  assert node.get_size() == MinNodeStruct.get_size()
  node.free()
  assert alloc.is_all_free()

