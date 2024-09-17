from amitools.vamos.machine import Machine
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.schedule import Scheduler, NativeTask, Stack
from amitools.vamos.machine.opcodes import *
from amitools.vamos.machine.regs import *


def setup():
    machine = Machine()
    sched = Scheduler(machine)
    alloc = MemoryAlloc.for_machine(machine)
    return machine, sched, alloc


def create_native_task(
    machine, alloc, pc, start_regs=None, return_regs=None, name=None
):
    if name is None:
        name = "task"
    stack = Stack.alloc(alloc, 4096)
    task = NativeTask(name, machine, pc, stack, start_regs, return_regs)
    return task


def schedule_scheduler_native_task_simple_test():
    machine, sched, alloc = setup()
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()
    mem.w16(pc, op_nop)
    mem.w16(pc + 2, op_rts)
    # add task
    task = create_native_task(machine, alloc, pc, {REG_D0: 42})
    assert sched.add_task(task)
    # run scheduler
    sched.schedule()
    result = task.get_result()
    assert result.regs == {REG_D0: 42}
    assert alloc.is_all_free()
    machine.cleanup()


def schedule_scheduler_native_task_cur_task_hook_test():
    tasks = []

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup()
    # set cur task callback
    sched.set_cur_task_callback(cb)

    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()
    mem.w16(pc, op_nop)
    mem.w16(pc + 2, op_rts)
    # add task
    task = create_native_task(machine, alloc, pc, {REG_D0: 42})
    assert sched.add_task(task)
    assert sched.get_cur_task() is None
    # run scheduler
    sched.schedule()
    result = task.get_result()
    assert result.regs == {REG_D0: 42}
    assert alloc.is_all_free()
    machine.cleanup()
    assert tasks == [task, None]


def schedule_scheduler_native_task_runner_test():
    tasks = []
    my_task = None

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup()
    sched.set_cur_task_callback(cb)
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()

    def trap(op, pc):
        my_task.run(pc2)

    addr = machine.setup_quick_trap(trap)

    # task setup
    mem.w16(pc, op_jmp)
    mem.w32(pc + 2, addr)
    mem.w16(pc + 6, op_rts)
    task = create_native_task(machine, alloc, pc, {REG_D0: 42})
    my_task = task

    # sub run
    pc2 = pc + 100
    mem.w16(pc2, op_nop)
    mem.w16(pc2 + 2, op_rts)

    # add task
    assert sched.add_task(task)
    # run scheduler
    sched.schedule()
    result = task.get_result()
    assert result.regs == {REG_D0: 42}
    assert alloc.is_all_free()
    machine.cleanup()
    assert tasks == [task, None]
