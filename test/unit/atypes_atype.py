from amitools.vamos.machine import MockMemory
from amitools.vamos.atypes import AmigaType, NodeType
from amitools.vamos.astructs import NodeStruct


def atypes_atype_node_base_test():
  @AmigaType(NodeStruct, wrap={'type' : NodeType})
  class MyNode:
    pass
  mem = MockMemory()
  n = MyNode(mem, 0)
  n.set_succ(1234)
  assert n.get_succ() == 1234
  n.set_type(NodeType.NT_LIBRARY)
  assert n.get_type() == NodeType(NodeType.NT_LIBRARY)


def atypes_atype_node_ctor_test():
  @AmigaType(NodeStruct, wrap={'type' : NodeType})
  class MyNode:
    def __init__(self, bla):
      self.bla = bla
  mem = MockMemory()
  n = MyNode(mem, 0, "hugo")
  assert n.bla == "hugo"
