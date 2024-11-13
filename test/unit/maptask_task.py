from amitools.vamos.machine import Machine
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.schedule import Scheduler, Code, TaskState, NativeTask, PythonTask
from amitools.vamos.maptask import MappedTask
from amitools.vamos.libtypes import Task
from amitools.vamos.machine.opcodes import *
from amitools.vamos.machine.regs import *


class Ctx:
    def __init__(self):
        self.machine = Machine()
        self.alloc = MemoryAlloc.for_machine(self.machine)

    def cleanup(self):
        assert self.alloc.is_all_free()
        self.machine.cleanup()


def setup():
    return Ctx()


def cleanup(ctx):
    ctx.cleanup()


class MyNativeTask:
    def __init__(self, ctx, name=None, **code_kw_args):
        if name is None:
            name = "task"
        self.ctx = ctx
        self.name = name
        self.stack = ctx.alloc.alloc_memory(4096, name + "_Stack")
        self.prog = ctx.alloc.alloc_memory(1024, name + "_Code")
        self.sp = self.stack.addr
        self.pc = self.prog.addr
        self.code = Code(self.pc, self.sp, **code_kw_args)
        self.sched_task = NativeTask(name, ctx.machine, self.code)
        self.ami_task = Task.alloc(ctx.alloc, name=name)
        self.map_task = MappedTask(self.sched_task, self.ami_task)

    def free(self):
        self.ami_task.free()
        self.ctx.alloc.free_memory(self.stack)
        self.ctx.alloc.free_memory(self.prog)


class MyPythonTask:
    def __init__(self, ctx, func=None, name=None, **code_kw_args):
        if name is None:
            name = "task"
        self.ctx = ctx
        self.name = name
        self.func = func
        self.stack = ctx.alloc.alloc_memory(4096, name + "_Stack")
        self.sp = self.stack.addr
        self.sched_task = PythonTask(name, ctx.machine, self.func, self.sp)
        self.ami_task = Task.alloc(ctx.alloc, name=name)
        self.map_task = MappedTask(self.sched_task, self.ami_task)

    def free(self):
        self.ami_task.free()
        self.ctx.alloc.free_memory(self.stack)


def create_both_tasks(ctx, name=None):
    return [
        MyNativeTask(ctx, name=name),
        MyPythonTask(ctx, name=name),
    ]


def check_task(task, name):
    # check ami values
    ami_task = task.get_ami_task()
    assert ami_task.name.str == name
    # check sched_task
    sched_task = task.get_sched_task()
    assert sched_task.get_name() == name


# test allocation of map task


def maptask_task_alloc_test():
    ctx = setup()
    for task_ctx in create_both_tasks(ctx, "foo"):
        map_task = task_ctx.map_task
        check_task(map_task, "foo")
        # clean up
        task_ctx.free()
    cleanup(ctx)


def maptask_task_state_test():
    ctx = setup()
    for task_ctx in create_both_tasks(ctx):
        map_task = task_ctx.map_task
        # set state and check if mapped state was updated
        map_task.get_sched_task().set_state(TaskState.TS_RUN)
        assert str(map_task.get_ami_task().tc_State) == TaskState.TS_RUN.name
        # clean up
        task_ctx.free()
    cleanup(ctx)


def maptask_task_sigmask_test():
    ctx = setup()
    for task_ctx in create_both_tasks(ctx):
        map_task = task_ctx.map_task
        # set state and check if mapped state was updated
        map_task.get_sched_task().set_signal(2, 2)
        assert map_task.get_ami_task().tc_SigRecvd.val == 2
        # clean up
        task_ctx.free()
    cleanup(ctx)
