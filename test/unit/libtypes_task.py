import pytest
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.libtypes import Task
from amitools.vamos.libstructs import TaskFlags, TaskState, NodeType


def libtypes_task_base_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    # alloc task
    name = "my_task"
    task = Task.alloc(alloc, name=name)
    assert task.name.str == name
    # task setup
    task.new_task(pri=-5, flags=TaskFlags.TF_LAUNCH)
    node = task.node
    assert node.type.val == NodeType.NT_TASK
    assert node.pri.val == -5
    assert task.flags.val == TaskFlags.TF_LAUNCH
    assert task.state.val == TaskState.TS_INVALID
    assert len(task.mem_entry) == 0
    assert task.mem_entry.type.val == NodeType.NT_MEMORY
    # done
    task.free()
    assert alloc.is_all_free()
