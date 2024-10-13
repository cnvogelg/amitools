from amitools.vamos.machine import Machine
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.schedule import Scheduler, NativeTask, VamosTask, Stack
from amitools.vamos.machine.opcodes import *
from amitools.vamos.machine.regs import *


def setup(slice_cycles=1000):
    machine = Machine()
    sched = Scheduler(machine, slice_cycles=slice_cycles)
    alloc = MemoryAlloc.for_machine(machine)
    return machine, sched, alloc


# ----- native tasks -----


def create_native_task(
    machine, alloc, pc, start_regs=None, return_regs=None, name=None
):
    if name is None:
        name = "task"
    stack = Stack.alloc(alloc, 4096)
    task = NativeTask(name, machine, stack, pc, start_regs, return_regs)
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
    exit_code = task.get_exit_code()
    assert exit_code == 42
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
    exit_code = task.get_exit_code()
    assert exit_code == 42
    assert alloc.is_all_free()
    machine.cleanup()
    assert tasks == [task, None]


def schedule_scheduler_native_task_subrun_test():
    tasks = []
    my_task = None

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup()
    sched.set_cur_task_callback(cb)
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()

    def trap(op, pc):
        my_task.sub_run(pc2)

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
    exit_code = task.get_exit_code()
    assert exit_code == 42
    assert alloc.is_all_free()
    machine.cleanup()
    assert tasks == [task, None]


def schedule_scheduler_native_task_remove_test():
    tasks = []
    my_task = None

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup()
    sched.set_cur_task_callback(cb)
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()

    def trap(op, pc):
        # remove my task to end execution
        sched.rem_task(my_task)

    addr = machine.setup_quick_trap(trap)

    # task setup
    mem.w16(pc, op_jmp)
    mem.w32(pc + 2, addr)
    mem.w16(pc + 6, op_jmp)
    mem.w32(pc + 8, pc)

    task = create_native_task(machine, alloc, pc, {REG_D0: 42})
    my_task = task

    # add task
    assert sched.add_task(task)
    # run scheduler
    sched.schedule()
    exit_code = task.get_exit_code()
    assert exit_code == 42
    assert alloc.is_all_free()
    machine.cleanup()
    assert tasks == [task, None]


def schedule_scheduler_native_task_multi_test():
    tasks = []
    my_task = None

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup(slice_cycles=30)
    sched.set_cur_task_callback(cb)
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()

    def trap1(op, pc):
        pass

    def trap2(op, pc):
        pass

    addr1 = machine.setup_quick_trap(trap1)
    addr2 = machine.setup_quick_trap(trap2)

    # task1 setup
    mem.w16(pc, op_jmp)
    mem.w32(pc + 2, addr1)
    off = pc + 6
    for i in range(100):
        mem.w16(off, op_nop)
        off += 2
    mem.w16(off, op_jmp)
    mem.w32(off + 2, addr2)
    mem.w16(off + 6, op_rts)

    task1 = create_native_task(machine, alloc, pc, {REG_D0: 42}, name="task1")
    my_task = task1

    # task2 setup
    pc2 = off + 8
    mem.w16(pc2, op_rts)

    task2 = create_native_task(machine, alloc, pc2, {REG_D0: 23}, name="task2")

    # add task
    assert sched.add_task(task1)
    assert sched.add_task(task2)
    # run scheduler
    sched.schedule()
    assert task1.get_exit_code() == 42
    assert task2.get_exit_code() == 23
    assert alloc.is_all_free()
    machine.cleanup()
    # check that the tasks switched
    assert tasks == [task1, task2, task1, None]


def schedule_scheduler_native_task_multi_forbid_test():
    tasks = []
    my_task = None

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup(slice_cycles=30)
    sched.set_cur_task_callback(cb)
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()

    def trap1(op, pc):
        my_task.forbid()

    def trap2(op, pc):
        my_task.permit()

    addr1 = machine.setup_quick_trap(trap1)
    addr2 = machine.setup_quick_trap(trap2)

    # task1 setup
    mem.w16(pc, op_jmp)
    mem.w32(pc + 2, addr1)
    off = pc + 6
    for i in range(100):
        mem.w16(off, op_nop)
        off += 2
    mem.w16(off, op_jmp)
    mem.w32(off + 2, addr2)
    mem.w16(off + 6, op_rts)

    task1 = create_native_task(machine, alloc, pc, {REG_D0: 42}, name="task1")
    my_task = task1

    # task2 setup
    pc2 = off + 8
    mem.w16(pc2, op_rts)

    task2 = create_native_task(machine, alloc, pc2, {REG_D0: 23}, name="task2")

    # add task
    assert sched.add_task(task1)
    assert sched.add_task(task2)
    # run scheduler
    sched.schedule()
    assert task1.get_exit_code() == 42
    assert task2.get_exit_code() == 23
    assert alloc.is_all_free()
    machine.cleanup()
    # check that the tasks switched
    assert tasks == [task1, task2, None]


def schedule_scheduler_native_task_multi_wait_test():
    tasks = []
    my_task = None

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup()
    sched.set_cur_task_callback(cb)
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()

    def trap1(op, pc):
        got = my_task.wait(3)
        assert got == 1

    def trap2(op, pc):
        my_task.set_signal(1, 1)

    addr1 = machine.setup_quick_trap(trap1)
    addr2 = machine.setup_quick_trap(trap2)

    # task1 setup
    mem.w16(pc, op_jmp)
    mem.w32(pc + 2, addr1)
    mem.w16(pc + 6, op_rts)

    task1 = create_native_task(machine, alloc, pc, {REG_D0: 42}, name="task1")
    my_task = task1

    # task2 setup
    pc2 = pc + 8
    mem.w16(pc2, op_jmp)
    mem.w32(pc2 + 2, addr2)
    mem.w16(pc2 + 6, op_rts)

    task2 = create_native_task(machine, alloc, pc2, {REG_D0: 23}, name="task2")

    # add task
    assert sched.add_task(task1)
    assert sched.add_task(task2)
    # run scheduler
    sched.schedule()
    assert task1.get_exit_code() == 42
    assert task2.get_exit_code() == 23
    assert alloc.is_all_free()
    machine.cleanup()
    # check that the tasks switched
    assert tasks == [task1, task2, task1, task2, None]


# ----- Vamos (Python) Tasks -----


def create_vamos_task(machine, alloc, run, name=None):
    if name is None:
        name = "task"
    stack = Stack.alloc(alloc, 4096)
    task = VamosTask(name, machine, stack, run)
    return task


def schedule_scheduler_vamos_task_simple_test():
    machine, sched, alloc = setup()

    def my_func(task):
        return 42

    # add task
    task = create_vamos_task(machine, alloc, my_func)
    assert sched.add_task(task)
    # run scheduler
    sched.schedule()
    exit_code = task.get_exit_code()
    assert exit_code == 42
    assert alloc.is_all_free()
    machine.cleanup()


def schedule_scheduler_vamos_task_cur_task_hook_test():
    tasks = []

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup()
    # set cur task callback
    sched.set_cur_task_callback(cb)

    def my_func(task):
        return 42

    # add task
    task = create_vamos_task(machine, alloc, my_func)
    assert sched.add_task(task)
    assert sched.get_cur_task() is None
    # run scheduler
    sched.schedule()
    exit_code = task.get_exit_code()
    assert exit_code == 42
    assert alloc.is_all_free()
    machine.cleanup()
    assert tasks == [task, None]


def schedule_scheduler_vamos_task_subrun_test():
    tasks = []

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup()
    sched.set_cur_task_callback(cb)
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()

    # sub run
    mem.w16(pc, op_nop)
    mem.w16(pc + 2, op_rts)

    def my_func(task):
        task.sub_run(pc)
        return 42

    task = create_vamos_task(machine, alloc, my_func)

    # add task
    assert sched.add_task(task)
    # run scheduler
    sched.schedule()
    exit_code = task.get_exit_code()
    assert exit_code == 42
    assert alloc.is_all_free()
    machine.cleanup()
    assert tasks == [task, None]


def schedule_scheduler_vamos_task_multi_test():
    tasks = []

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup(slice_cycles=30)
    sched.set_cur_task_callback(cb)

    def task1_run(task):
        # coop multi tasking!
        task.reschedule()
        return 42

    def task2_run(task):
        # coop multi tasking!
        task.reschedule()
        return 23

    task1 = create_vamos_task(machine, alloc, task1_run, name="task1")
    task2 = create_vamos_task(machine, alloc, task2_run, name="task2")

    # add task
    assert sched.add_task(task1)
    assert sched.add_task(task2)
    # run scheduler
    sched.schedule()
    assert task1.get_exit_code() == 42
    assert task2.get_exit_code() == 23
    assert alloc.is_all_free()
    machine.cleanup()
    # check that the tasks switched
    assert tasks == [task1, task2, task1, task2, None]


def schedule_scheduler_vamos_task_multi_forbid_test():
    tasks = []

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup(slice_cycles=30)
    sched.set_cur_task_callback(cb)

    def task1_run(task):
        task.forbid()
        # coop multi tasking!
        # but does not switch due to forbid state
        task.reschedule()
        task.permit()
        return 42

    def task2_run(task):
        # coop multi tasking!
        task.reschedule()
        return 23

    task1 = create_vamos_task(machine, alloc, task1_run, name="task1")
    task2 = create_vamos_task(machine, alloc, task2_run, name="task2")

    # add task
    assert sched.add_task(task1)
    assert sched.add_task(task2)
    # run scheduler
    sched.schedule()
    assert task1.get_exit_code() == 42
    assert task2.get_exit_code() == 23
    assert alloc.is_all_free()
    machine.cleanup()
    # check that the tasks switched
    assert tasks == [task1, task2, task1, task2, None]


def schedule_scheduler_vamos_task_multi_wait_test():
    tasks = []

    def cb(task):
        tasks.append(task)

    machine, sched, alloc = setup(slice_cycles=30)
    sched.set_cur_task_callback(cb)

    def task1_run(task):
        got = task.wait(3)
        assert got == 1
        return 42

    def task2_run(task):
        task1.set_signal(1, 1)
        return 23

    task1 = create_vamos_task(machine, alloc, task1_run, name="task1")
    task2 = create_vamos_task(machine, alloc, task2_run, name="task2")

    # add task
    assert sched.add_task(task1)
    assert sched.add_task(task2)
    # run scheduler
    sched.schedule()
    assert task1.get_exit_code() == 42
    assert task2.get_exit_code() == 23
    assert alloc.is_all_free()
    machine.cleanup()
    # check that the tasks switched
    assert tasks == [task1, task2, task1, task2, None]
