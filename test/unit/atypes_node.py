from amitools.vamos.machine import MockMemory
from amitools.vamos.atypes import Node, NodeType


def libnative_node_base_test():
  mem = MockMemory()
  text = 'hello, world!'
  mem.w_cstr(0, text)
  node = Node(mem, 0x42)
  # set node
  node.set_succ(1234)
  node.set_pred(5678)
  node.set_type(NodeType.NT_LIBRARY)
  node.set_pri(-3)
  node.set_name_addr(0)
  # check node
  assert node.get_succ() == 1234
  assert node.get_pred() == 5678
  assert node.get_type() == NodeType.NT_LIBRARY
  assert node.get_pri() == -3
  assert node.get_name_addr() == 0
  assert node.get_name() == text


def libnative_node_setup_test():
  mem = MockMemory()
  text = 'hello, world!'
  mem.w_cstr(12, text)
  node = Node(mem, 0x42)
  node.setup(1234, 5678, NodeType.NT_DEVICE, -5, 12)
  # check node
  assert node.get_succ() == 1234
  assert node.get_pred() == 5678
  assert node.get_type() == NodeType.NT_DEVICE
  assert node.get_pri() == -5
  assert node.get_name_addr() == 12
  assert node.get_name() == text


def libnative_node_min_setup_test():
  mem = MockMemory()
  node = Node(mem, 0x42)
  node.min_setup(1234, 5678)
  # check node
  assert node.get_succ() == 1234
  assert node.get_pred() == 5678


def libnative_node_str_test():
  mem = MockMemory()
  text = 'hello, world!'
  mem.w_cstr(12, text)
  node = Node(mem, 0x42)
  node.setup(0x1234, 0x5678, NodeType.NT_DEVICE, -5, 12)
  assert str(node) == \
      "[Node:@000042,p=005678,s=001234,NT_DEVICE,-5,'hello, world!']"
  min_node = Node(mem, 0x80, True)
  min_node.min_setup(0x1234, 0x5678)
  assert str(min_node) == "[MinNode:@000080,p=005678,s=001234]"
