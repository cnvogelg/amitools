import pytest

from amitools.vamos.libtypes import Task
from amitools.vamos.machine import Machine, REG_D0, REG_D1, REG_D2, REG_A0
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.task import ExecTask, DosProcess


@pytest.fixture
def context():
    machine = Machine()
    alloc = MemoryAlloc.for_machine(machine)
    yield machine, alloc, machine.get_mem()
    assert alloc.is_all_free()
    machine.cleanup()


@pytest.mark.parametrize("task_type", [ExecTask, DosProcess])
@pytest.mark.parametrize("stack_size", [None, 16384])
@pytest.mark.parametrize("native", [False, True])
def task_stack_bounds_test(context, task_type, stack_size, native):
    machine, alloc, mem = context
    kwargs = {} if stack_size is None else {"stack_size": stack_size}
    start_regs = {}
    code = None
    if native:
        code = alloc.alloc_memory(12)
        # Read tc_SPLower/tc_SPUpper at their public ABI offsets into D1/D2,
        # then return 42: move.l 58(a0),d1; move.l 62(a0),d2; moveq; rts.
        mem.w_block(code.addr, bytes.fromhex("2228003a2428003e702a4e75"))
        kwargs.update(
            start_pc=code.addr,
            start_regs=start_regs,
            return_regs=[REG_D0, REG_D1, REG_D2],
        )
    else:

        def run(sched_task):
            mapped = sched_task.map_task
            task = mapped.get_ami_task()
            stack = mapped.get_stack()
            assert task.tc_SPLower.aptr == stack.get_lower()
            assert task.tc_SPUpper.aptr == stack.get_upper()
            return 42

        kwargs["func"] = run
    mapped = task_type(machine, alloc, "bounds", **kwargs)
    try:
        task = mapped.get_ami_task()
        stack = mapped.get_stack()
        assert stack.get_size() == (4096 if stack_size is None else stack_size)
        assert mem.r32(task.addr + 58) == stack.get_lower()
        assert mem.r32(task.addr + 62) == stack.get_upper()
        assert stack.get_lower() <= stack.get_initial_sp() < stack.get_upper()
        start_regs[REG_A0] = task.addr
        sched_task = mapped.get_sched_task()
        sched_task.start()
        assert sched_task.get_error() is None
        assert sched_task.get_exit_code() == 42
        if native:
            registers = sched_task.get_return_regs()
            assert registers[REG_D1] == stack.get_lower()
            assert registers[REG_D2] == stack.get_upper()
    finally:
        mapped.free()
        if code is not None:
            alloc.free_memory(code)


def task_stack_bounds_borrowed_task_test(context):
    machine, alloc, _ = context
    task = Task.alloc(alloc, name="borrowed")
    task.new_task()
    task.tc_SPLower.aptr = 0x1111
    task.tc_SPUpper.aptr = 0x2222
    free_before = alloc.get_free_bytes()
    try:
        mapped = ExecTask(machine, alloc, "bounds", ami_task=task, func=lambda _: 0)
        try:
            assert not mapped.own_task
            assert task.tc_SPLower.aptr == mapped.get_stack().get_lower()
            assert task.tc_SPUpper.aptr == mapped.get_stack().get_upper()
        finally:
            mapped.free()
        # Releasing the mapped task frees its stack but leaves the supplied
        # Task and its name allocation owned by the caller.
        assert alloc.get_free_bytes() == free_before
    finally:
        task.free()


def task_stack_bounds_independent_tasks_test(context):
    machine, alloc, _ = context
    first = ExecTask(machine, alloc, "first", func=lambda _: 0)
    second = DosProcess(machine, alloc, "second", func=lambda _: 0)
    first_bounds = (first.task.tc_SPLower.aptr, first.task.tc_SPUpper.aptr)
    second_bounds = (second.task.tc_SPLower.aptr, second.task.tc_SPUpper.aptr)
    try:
        assert first_bounds != second_bounds
        assert (
            first_bounds[1] <= second_bounds[0] or second_bounds[1] <= first_bounds[0]
        )
        first.free()
        first = None
        assert (
            second.task.tc_SPLower.aptr,
            second.task.tc_SPUpper.aptr,
        ) == second_bounds
        second.get_sched_task().start()
        assert second.get_sched_task().get_exit_code() == 0
    finally:
        if first is not None:
            first.free()
        second.free()
