from types import SimpleNamespace

from amitools.vamos.lib.lexec.taskfunc import TaskMixin
from amitools.vamos.libstructs import TaskStruct, TaskState
from amitools.vamos.libtypes import Task
from amitools.vamos.machine import Machine
from amitools.vamos.machine.backend import Machine68kBackend
from amitools.vamos.schedule import Scheduler
from lib_exec_helper import ExecHost, make_exec_lib


class Host(ExecHost, TaskMixin):
    pass


def _make_task(mem, alloc, name="task"):
    task_struct = alloc.alloc_astruct(TaskStruct, label=name)
    task = Task(mem, task_struct.addr)
    task.new_task()
    task.node.name.aptr = alloc.alloc_cstr(name, label=name + "_name").addr
    stack = alloc.alloc_memory(0x100, label=name + "_stack")
    task.sp_lower.aptr = stack.addr
    task.sp_upper.aptr = stack.addr + 0x100
    task.sp_reg.aptr = stack.addr + 0x100
    return task


def _host_with_task():
    mem, alloc, el = make_exec_lib()
    task = _make_task(mem, alloc)
    fake = SimpleNamespace(get_ami_task=lambda: task, get_sched_task=lambda: None)
    return Host(mem, alloc, el, task=fake), task


def exec_set_except_test():
    host, task = _host_with_task()
    task.sig_except.val = 0x0F
    old = host.SetExcept(host.ctx, 0x30, 0x3C)
    assert old == 0x0F
    # (old & ~mask) | (new & mask)
    assert task.sig_except.val == 0x33


def exec_alloc_free_trap_test():
    host, task = _host_with_task()
    assert task.trap_alloc.val == 0
    assert host.AllocTrap(host.ctx, 4) == 4
    assert task.trap_alloc.val == 1 << 4
    # a specific trap already in use fails
    assert host.AllocTrap(host.ctx, 4) == -1
    # -1 picks the first free trap
    assert host.AllocTrap(host.ctx, -1) == 0
    assert task.trap_alloc.val == (1 << 4) | 1
    host.FreeTrap(host.ctx, 4)
    assert task.trap_alloc.val == 1
    # -1 is ignored
    host.FreeTrap(host.ctx, -1)
    assert task.trap_alloc.val == 1


def exec_add_remove_task_test():
    machine = Machine(Machine68kBackend().create_machine("68000"))
    try:
        mem, alloc, el = make_exec_lib(mem=machine.mem)
        task = _make_task(mem, alloc)
        scheduler = Scheduler(machine)
        fake = SimpleNamespace(get_ami_task=lambda: task, get_sched_task=lambda: None)
        host = Host(
            mem,
            alloc,
            el,
            cpu=machine.cpu,
            task=fake,
            scheduler=scheduler,
            machine=machine,
        )
        sp_before = task.sp_reg.aptr
        assert host.AddTask(host.ctx, task, 0x2000, 0x3000) == task.addr
        # one scheduler task was created and mapped to the ami Task
        assert len(scheduler.ready_tasks) == 1
        sched_task = scheduler.ready_tasks[0]
        assert sched_task.map_task.ami_task.addr == task.addr
        # exec pushes the final PC as the initial return address
        assert task.sp_reg.aptr == sp_before - 4
        assert mem.r32(task.sp_reg.aptr) == 0x3000
        # removing it again unlinks the scheduler task
        host.RemTask(host.ctx, task)
        assert scheduler.ready_tasks == []
        assert task.state.val == TaskState.TS_REMOVED
    finally:
        machine.cleanup()
