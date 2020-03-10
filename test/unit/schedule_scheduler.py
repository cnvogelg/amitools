from amitools.vamos.machine import Machine
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.schedule import Scheduler, Task, Stack
from amitools.vamos.machine.opcodes import *
from amitools.vamos.machine.regs import *


def setup():
    machine = Machine()
    sched = Scheduler(machine)
    alloc = MemoryAlloc.for_machine(machine)
    return machine, sched, alloc


def create_task(alloc, pc, start_regs=None, return_regs=None, name=None):
    if name is None:
        name = "task"
    stack = Stack.alloc(alloc, 4096)
    task = Task(name, pc, stack, start_regs, return_regs)
    return task


def schedule_scheduler_simple_task_test():
    machine, sched, alloc = setup()
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()
    mem.w16(pc, op_nop)
    mem.w16(pc + 2, op_rts)
    task = create_task(alloc, pc, {REG_D0: 42})
    assert sched.add_task(task)
    assert sched.schedule() is None
    assert sched.get_num_tasks() == 0
    assert task.get_result_regs() == {REG_D0: 42}
    assert alloc.is_all_free()
    machine.cleanup()


def schedule_scheduler_cb_test():
    tasks = []

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup()
    sched.set_cur_task_callback(cb)
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()
    mem.w16(pc, op_nop)
    mem.w16(pc + 2, op_rts)
    task = create_task(alloc, pc, {REG_D0: 42})
    assert sched.add_task(task)
    assert sched.schedule() is None
    assert sched.get_num_tasks() == 0
    assert task.get_result_regs() == {REG_D0: 42}
    assert alloc.is_all_free()
    machine.cleanup()
    assert tasks == [task, None]


def schedule_scheduler_recursive_add_test():
    tasks = []

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup()
    sched.set_cur_task_callback(cb)
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()
    pc2 = pc + 100
    mem.w16(pc2, op_nop)
    mem.w16(pc2 + 2, op_rts)
    task2 = create_task(alloc, pc2, {REG_D0: 23})

    def trap(op, pc):
        assert sched.add_task(task2)

    addr = machine.setup_quick_trap(trap)
    mem.w16(pc, op_jmp)
    mem.w32(pc + 2, addr)
    mem.w16(pc + 6, op_rts)
    task = create_task(alloc, pc, {REG_D0: 42})
    assert sched.add_task(task)
    assert sched.schedule() is None
    assert sched.get_num_tasks() == 0
    assert task.get_result_regs() == {REG_D0: 42}
    assert task2.get_result_regs() == {REG_D0: 23}
    assert alloc.is_all_free()
    machine.cleanup()
    assert tasks == [task, task2, task, None]


def schedule_scheduler_sub_task_test():
    tasks = []

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup()
    sched.set_cur_task_callback(cb)
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()
    pc2 = pc + 100
    mem.w16(pc2, op_nop)
    mem.w16(pc2 + 2, op_rts)
    task2 = create_task(alloc, pc2, {REG_D0: 23}, name="sub")

    def trap(op, pc):
        assert sched.run_sub_task(task2)

    addr = machine.setup_quick_trap(trap)
    mem.w16(pc, op_jmp)
    mem.w32(pc + 2, addr)
    mem.w16(pc + 6, op_rts)
    task = create_task(alloc, pc, {REG_D0: 42})
    assert sched.add_task(task)
    assert sched.schedule() is None
    assert sched.get_num_tasks() == 0
    assert task.get_result_regs() == {REG_D0: 42}
    assert task2.get_result_regs() == {REG_D0: 23}
    assert alloc.is_all_free()
    machine.cleanup()
    assert tasks == [task, None]
