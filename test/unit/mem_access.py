import pytest
from amitools.vamos.lib.lexec.ExecStruct import NodeDef, TaskDef
from amitools.vamos.mem import AccessStruct
from amitools.vamos.machine import MockMemory


def mem_access_rw_all_node_test():
  mem = MockMemory()
  a = AccessStruct(mem, NodeDef, 0x42)
  data = a.r_all()
  print(data)
  a.w_all(data)


def mem_access_rw_all_task_test():
  mem = MockMemory()
  a = AccessStruct(mem, TaskDef, 0x42)
  data = a.r_all()
  print(data)
  a.w_all(data)


def mem_access_rw_field_node_test():
  mem = MockMemory()
  a = AccessStruct(mem, NodeDef, 0x42)
  a.w_s('ln_Succ', 42)
  a.w_s('ln_Pred', 21)
  assert a.r_s('ln_Succ') == 42
  assert a.r_s('ln_Pred') == 21


def mem_access_rw_sub_field_task_test():
  mem = MockMemory()
  a = AccessStruct(mem, TaskDef, 0x42)
  a.w_s('tc_Node.ln_Succ', 42)
  a.w_s('tc_Node.ln_Pred', 21)
  assert a.r_s('tc_Node.ln_Succ') == 42
  assert a.r_s('tc_Node.ln_Pred') == 21


def mem_access_invalid_node_test():
  mem = MockMemory()
  a = AccessStruct(mem, NodeDef, 0x42)
  with pytest.raises(ValueError):
    a.w_s('bla', 12)
  with pytest.raises(ValueError):
    a.r_s('blub', 12)
