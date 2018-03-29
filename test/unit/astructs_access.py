import pytest
from amitools.vamos.astructs import AccessStruct, NodeStruct, TaskStruct
from amitools.vamos.machine import MockMemory


def mem_access_rw_all_node_test():
  mem = MockMemory()
  a = AccessStruct(mem, NodeStruct, 0x42)
  data = a.r_all()
  print(data)
  a.w_all(data)


def mem_access_rw_all_task_test():
  mem = MockMemory()
  a = AccessStruct(mem, TaskStruct, 0x42)
  data = a.r_all()
  print(data)
  a.w_all(data)


def mem_access_rw_field_node_test():
  mem = MockMemory()
  a = AccessStruct(mem, NodeStruct, 0x42)
  a.w_s('ln_Succ', 42)
  a.w_s('ln_Pred', 21)
  a.w_s('ln_Pri', -27)
  assert a.r_s('ln_Succ') == 42
  assert a.r_s('ln_Pred') == 21
  assert a.r_s('ln_Pri') == -27


def mem_access_rw_sub_field_task_test():
  mem = MockMemory()
  a = AccessStruct(mem, TaskStruct, 0x42)
  a.w_s('tc_Node.ln_Succ', 42)
  a.w_s('tc_Node.ln_Pred', 21)
  assert a.r_s('tc_Node.ln_Succ') == 42
  assert a.r_s('tc_Node.ln_Pred') == 21


def mem_access_invalid_node_test():
  mem = MockMemory()
  a = AccessStruct(mem, NodeStruct, 0x42)
  with pytest.raises(KeyError):
    a.w_s('bla', 12)
  with pytest.raises(KeyError):
    a.r_s('blub', 12)


def mem_access_s_get_addr_test():
  mem = MockMemory()
  a = AccessStruct(mem, NodeStruct, 0x42)
  assert a.s_get_addr('ln_Succ') == 0x42
  assert a.s_get_addr('ln_Pred') == 0x46
