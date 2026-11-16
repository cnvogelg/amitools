from amitools.vamos.machine import (
    Machine,
    Code,
    REG_D0,
    op_nop,
    op_rts,
    op_reset,
    CPUHWExceptionError,
)
from amitools.vamos.schedule import NativeTask, PythonTask, Scheduler, TaskState
import pytest


def create_native_task(machine, pc, sp, name=None, **kw_args):
    if name is None:
        name = "task"
    code = Code(pc, sp, **kw_args)
    task = NativeTask(name, machine, code)
    return task


def create_python_task(machine, func, sp, name=None):
    if name is None:
        name = "task"
    task = PythonTask(name, machine, func, sp)
    return task


def schedule_task_native_simple_test():
    machine = Machine()

    pc = machine.get_scratch_begin()
    sp = machine.get_scratch_top()
    task = create_native_task(machine, pc, sp, set_regs={REG_D0: 42})

    mem = machine.get_mem()
    mem.w16(pc, op_nop)
    mem.w16(pc + 2, op_rts)

    exit_code = task.start()
    assert exit_code == 42
    assert task.get_exit_code() == 42
    assert task.get_error() is None

    machine.cleanup()


def schedule_task_native_mach_error_test():
    machine = Machine()

    pc = machine.get_scratch_begin()
    sp = machine.get_scratch_top()
    task = create_native_task(machine, pc, sp, set_regs={REG_D0: 42})

    mem = machine.get_mem()
    mem.w16(pc, op_nop)
    mem.w16(pc + 2, op_reset)

    mach_error = task.start()
    assert type(mach_error) is CPUHWExceptionError
    assert task.get_exit_code() is None
    assert task.get_error() is mach_error

    machine.cleanup()


def schedule_task_python_simple_test():
    machine = Machine()

    def my_func(task):
        return 42

    sp = machine.get_scratch_top()
    task = create_python_task(machine, my_func, sp)

    exit_code = task.start()
    assert exit_code == 42
    assert task.get_exit_code() == 42

    machine.cleanup()


@pytest.mark.parametrize("native", [False, True])
def schedule_task_exception_removal_test(native, monkeypatch):
    machine = Machine()
    scheduler = Scheduler(machine)

    def fail(*args):
        raise RuntimeError("task failed")

    if native:
        task = create_native_task(
            machine, machine.get_scratch_begin(), machine.get_scratch_top()
        )
        monkeypatch.setattr(task.runtime, "start", fail)
    else:
        task = create_python_task(machine, fail, machine.get_scratch_top())
    scheduler.add_task(task)
    with pytest.raises(RuntimeError, match="task failed"):
        scheduler.run_until_idle()
    assert task.get_state() == TaskState.TS_REMOVED
    assert scheduler.get_num_tasks() == 0
    # Shutdown can enter the scheduler again without reviving the failed task.
    cleanup = PythonTask("cleanup", machine, lambda task: 7)
    scheduler.add_task(cleanup)
    scheduler.run_until_idle()
    assert cleanup.get_exit_code() == 7
    machine.cleanup()
