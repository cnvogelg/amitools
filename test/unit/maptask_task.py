from amitools.vamos.machine import Machine
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.schedule import Scheduler, Code, TaskState, NativeTask
from amitools.vamos.maptask import MappedTask, TaskCtx
from amitools.vamos.machine.opcodes import *
from amitools.vamos.machine.regs import *


def setup(slice_cycles=1000):
    machine = Machine()
    alloc = MemoryAlloc.for_machine(machine)
    task_ctx = TaskCtx(machine, alloc)
    return task_ctx


def create_native_task(
    task_ctx, code=None, start_regs=None, return_regs=None, name="foo"
):
    if name is None:
        name = "task"
    if code is None:
        code = Code.alloc(
            task_ctx.alloc, 256, start_regs=start_regs, return_regs=return_regs
        )
    return MappedTask.from_native_code(task_ctx, name, code)


def create_python_task(task_ctx, func=None, name="foo"):
    if name is None:
        name = "task"
    if func is None:

        def func(ctx, task):
            assert task_ctx == ctx

    return MappedTask.from_python_code(task_ctx, name, func)


def create_both_tasks(task_ctx):
    return [
        create_native_task(task_ctx),
        create_python_task(task_ctx),
    ]


def check_task(task_ctx, task):
    # check ami values
    ami_task = task.get_ami_task()
    assert ami_task.name.str == "foo"
    # check sched_task
    sched_task = task.get_sched_task()
    assert sched_task.get_name() == "foo"
    # check stack values
    stack = sched_task.get_stack()
    assert ami_task.tc_SPReg.aptr == stack.get_initial_sp()
    assert ami_task.tc_SPLower.aptr == stack.get_lower()
    assert ami_task.tc_SPUpper.aptr == stack.get_upper()
    # in memory
    mem = task_ctx.machine.get_mem()
    addr = ami_task.addr
    assert mem.r32(addr + ami_task.sdef.tc_SPReg.offset) == stack.get_initial_sp()
    assert mem.r32(addr + ami_task.sdef.tc_SPLower.offset) == stack.get_lower()
    assert mem.r32(addr + ami_task.sdef.tc_SPUpper.offset) == stack.get_upper()


# test allocation of map task


def maptask_task_alloc_test():
    task_ctx = setup()
    for task in create_both_tasks(task_ctx):
        check_task(task_ctx, task)
        if type(task.get_sched_task()) is NativeTask:
            assert task.get_code() is not None
        else:
            assert task.get_code() is None
        # clean up
        task.free()
    assert task_ctx.alloc.is_all_free()
    task_ctx.machine.cleanup()


def maptask_task_state_test():
    task_ctx = setup()
    for task in create_both_tasks(task_ctx):
        # set state and check if mapped state was updated
        task.get_sched_task().set_state(TaskState.TS_RUN)
        assert str(task.get_ami_task().tc_State) == TaskState.TS_RUN.name
        # clean up
        task.free()
    assert task_ctx.alloc.is_all_free()
    task_ctx.machine.cleanup()


def maptask_task_sigmask_test():
    task_ctx = setup()
    for task in create_both_tasks(task_ctx):
        # set state and check if mapped state was updated
        task.get_sched_task().set_signal(2, 2)
        assert task.get_ami_task().tc_SigRecvd.val == 2
        # clean up
        task.free()
    assert task_ctx.alloc.is_all_free()
    task_ctx.machine.cleanup()
