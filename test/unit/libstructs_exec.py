import pytest
from amitools.vamos.libstructs import NodeStruct, TaskStruct, ExecLibraryStruct
from amitools.vamos.machine import MockMemory


def libstructs_exec_node_test():
    mem = MockMemory()
    node = NodeStruct(mem, 0x42)
    node.ln_Succ.set(42)
    node.ln_Pred.set(21)
    node.ln_Pri.set(-27)
    assert node.ln_Succ.get() == 42
    assert node.ln_Pred.get() == 21
    assert node.ln_Pri.get() == -27


def libstructs_exec_task_test():
    mem = MockMemory()
    task = TaskStruct(mem, 0x40)
    task.tc_Node.ln_Succ.set(42)
    task.tc_Node.ln_Pred.set(21)
    assert task.tc_Node.ln_Succ.get() == 42
    assert task.tc_Node.ln_Pred.get() == 21


def libstructs_exec_execbase_test():
    mem = MockMemory()
    execbase = ExecLibraryStruct(mem, 0x100)
    assert execbase.get_byte_size() == 634
