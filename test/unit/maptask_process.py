from amitools.vamos.machine import Machine
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.schedule import Scheduler, Code, TaskState, NativeTask
from amitools.vamos.maptask import MappedProcess, TaskCtx
from amitools.vamos.machine.opcodes import *
from amitools.vamos.machine.regs import *


def setup(slice_cycles=1000):
    machine = Machine()
    alloc = MemoryAlloc.for_machine(machine)
    task_ctx = TaskCtx(machine, alloc)
    return task_ctx


def create_native_process(
    task_ctx, code=None, start_regs=None, return_regs=None, name="foo"
):
    if name is None:
        name = "proc"
    if code is None:
        code = Code.alloc(
            task_ctx.alloc, 256, start_regs=start_regs, return_regs=return_regs
        )
    return MappedProcess.from_native_code(task_ctx, name, code)


def create_python_process(task_ctx, func=None, name="foo"):
    if name is None:
        name = "proc"
    if func is None:

        def func(ctx, task):
            assert task_ctx == ctx

    return MappedProcess.from_python_code(task_ctx, name, func)


def create_both_processes(task_ctx):
    return [
        create_native_process(task_ctx),
        create_python_process(task_ctx),
    ]


def check_process(task_ctx, proc):
    # check ami values
    ami_process = proc.get_ami_process()
    assert ami_process.name.str == "foo"
    # check sched_process
    sched_task = proc.get_sched_task()
    assert sched_task.get_name() == "foo"


# test allocation of map task


def maptask_process_alloc_test():
    task_ctx = setup()
    for proc in create_both_processes(task_ctx):
        check_process(task_ctx, proc)
        if type(proc.get_sched_task()) is NativeTask:
            assert proc.get_code() is not None
        else:
            assert proc.get_code() is None
        # clean up
        proc.free()
    assert task_ctx.alloc.is_all_free()
    task_ctx.machine.cleanup()


def maptask_process_state_test():
    task_ctx = setup()
    for proc in create_both_processes(task_ctx):
        # set state and check if mapped state was updated
        proc.get_sched_task().set_state(TaskState.TS_RUN)
        assert str(proc.get_ami_task().tc_State) == TaskState.TS_RUN.name
        # clean up
        proc.free()
    assert task_ctx.alloc.is_all_free()
    task_ctx.machine.cleanup()


def maptask_process_sigmask_test():
    task_ctx = setup()
    for proc in create_both_processes(task_ctx):
        # set state and check if mapped state was updated
        proc.get_sched_task().set_signal(2, 2)
        assert proc.get_ami_task().tc_SigRecvd.val == 2
        # clean up
        proc.free()
    assert task_ctx.alloc.is_all_free()
    task_ctx.machine.cleanup()
