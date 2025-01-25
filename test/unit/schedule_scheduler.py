from amitools.vamos.machine import Machine, Code
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.schedule import (
    Scheduler,
    NativeTask,
    PythonTask,
    SchedulerEvent,
    SchedulerConfig,
)
from amitools.vamos.machine.opcodes import *
from amitools.vamos.machine.regs import *


class Ctx:
    def __init__(self, machine, sched, alloc, events):
        self.machine = machine
        self.sched = sched
        self.alloc = alloc
        self.mem = machine.get_mem()
        self.events = events


def setup(slice_cycles=1000):
    machine = Machine()
    cfg = SchedulerConfig(slice_cycles)
    sched = Scheduler(machine, cfg)
    alloc = MemoryAlloc.for_machine(machine)

    events = []

    def cb(event):
        events.append(event)

    sched.set_event_callback(cb)

    return Ctx(machine, sched, alloc, events)


def cleanup(ctx):
    assert ctx.alloc.is_all_free()
    ctx.machine.cleanup()


# ----- native tasks -----


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
        self.task = NativeTask(name, ctx.machine, self.code)

    def free(self):
        self.ctx.alloc.free_memory(self.stack)
        self.ctx.alloc.free_memory(self.prog)


def schedule_scheduler_native_task_simple_test():
    ctx = setup()

    # prepare task
    task_ctx = MyNativeTask(ctx, set_regs={REG_D0: 42})

    pc = task_ctx.pc
    ctx.mem.w16(pc, op_nop)
    ctx.mem.w16(pc + 2, op_rts)

    # add task
    task = task_ctx.task
    assert ctx.sched.add_task(task)

    # run scheduler to run task
    ctx.sched.schedule()
    exit_code = task.get_exit_code()
    assert exit_code == 42

    task_ctx.free()
    cleanup(ctx)


def schedule_scheduler_native_task_event_hook_test():
    ctx = setup()
    # set cur task callback
    sched = ctx.sched

    task_ctx = MyNativeTask(ctx, set_regs={REG_D0: 42})
    task = task_ctx.task

    pc = task_ctx.pc
    ctx.mem.w16(pc, op_nop)
    ctx.mem.w16(pc + 2, op_rts)

    # add task
    assert sched.add_task(task)
    assert sched.get_cur_task() is None
    # run scheduler
    sched.schedule()
    exit_code = task.get_exit_code()
    assert exit_code == 42

    assert ctx.events == [
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
    ]

    task_ctx.free()
    cleanup(ctx)


def schedule_scheduler_native_task_subrun_test():
    my_task = None

    ctx = setup()
    sched = ctx.sched

    task_ctx = MyNativeTask(ctx, set_regs={REG_D0: 42})
    task = task_ctx.task
    my_task = task

    mem = ctx.mem
    pc = task_ctx.pc

    def trap(op, pc):
        my_task.sub_run(Code(pc2))

    addr = ctx.machine.setup_quick_trap(trap)

    # task setup
    mem.w16(pc, op_jmp)
    mem.w32(pc + 2, addr)
    mem.w16(pc + 6, op_rts)

    # sub run
    pc2 = pc + 8
    mem.w16(pc2, op_nop)
    mem.w16(pc2 + 2, op_rts)

    # add task
    assert sched.add_task(task)
    # run scheduler
    sched.schedule()
    exit_code = task.get_exit_code()
    assert exit_code == 42

    assert ctx.events == [
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
    ]

    task_ctx.free()
    cleanup(ctx)


def schedule_scheduler_native_task_remove_test():
    my_task = None

    ctx = setup()
    sched = ctx.sched

    task_ctx = MyNativeTask(ctx, set_regs={REG_D0: 42})
    task = task_ctx.task
    my_task = task

    mem = ctx.mem
    pc = task_ctx.pc

    def trap(op, pc):
        # remove my task to end execution
        sched.rem_task(my_task)

    addr = ctx.machine.setup_quick_trap(trap)

    # task setup
    mem.w16(pc, op_jmp)
    mem.w32(pc + 2, addr)
    mem.w16(pc + 6, op_jmp)
    mem.w32(pc + 8, pc)

    # add task
    assert sched.add_task(task)
    # run scheduler
    sched.schedule()
    exit_code = task.get_exit_code()
    assert exit_code == 42

    assert ctx.events == [
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
    ]

    task_ctx.free()
    cleanup(ctx)


def schedule_scheduler_native_task_multi_test():
    my_task = None

    ctx = setup(slice_cycles=30)
    sched = ctx.sched

    mem = ctx.mem

    def trap1(op, pc):
        pass

    def trap2(op, pc):
        pass

    addr1 = ctx.machine.setup_quick_trap(trap1)
    addr2 = ctx.machine.setup_quick_trap(trap2)

    task1_ctx = MyNativeTask(ctx, set_regs={REG_D0: 42}, name="task1")
    task1 = task1_ctx.task
    my_task = task1

    pc = task1_ctx.pc

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

    task2_ctx = MyNativeTask(ctx, set_regs={REG_D0: 23}, name="task2")
    task2 = task2_ctx.task

    # task2 setup
    pc2 = task2_ctx.pc
    mem.w16(pc2, op_rts)

    # add task
    assert sched.add_task(task1)
    assert sched.add_task(task2)
    # run scheduler
    sched.schedule()
    assert task1.get_exit_code() == 42
    assert task2.get_exit_code() == 23

    # check that the tasks switched
    assert ctx.events == [
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.READY_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
    ]

    task2_ctx.free()
    task1_ctx.free()
    cleanup(ctx)


def schedule_scheduler_native_task_multi_forbid_test():
    my_task = None

    ctx = setup(slice_cycles=30)
    sched = ctx.sched
    mem = ctx.mem

    def trap1(op, pc):
        my_task.forbid()

    def trap2(op, pc):
        my_task.permit()

    addr1 = ctx.machine.setup_quick_trap(trap1)
    addr2 = ctx.machine.setup_quick_trap(trap2)

    task1_ctx = MyNativeTask(ctx, set_regs={REG_D0: 42}, name="task1")
    task1 = task1_ctx.task
    my_task = task1

    # task1 setup
    pc = task1_ctx.pc
    mem.w16(pc, op_jmp)
    mem.w32(pc + 2, addr1)
    off = pc + 6
    for i in range(100):
        mem.w16(off, op_nop)
        off += 2
    mem.w16(off, op_jmp)
    mem.w32(off + 2, addr2)
    mem.w16(off + 6, op_rts)

    task2_ctx = MyNativeTask(ctx, set_regs={REG_D0: 23}, name="task2")
    task2 = task2_ctx.task

    # task2 setup
    pc2 = task2_ctx.pc
    mem.w16(pc2, op_rts)

    # add task
    assert sched.add_task(task1)
    assert sched.add_task(task2)
    # run scheduler
    sched.schedule()
    assert task1.get_exit_code() == 42
    assert task2.get_exit_code() == 23

    # check that the tasks switched
    assert ctx.events == [
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
    ]

    task2_ctx.free()
    task1_ctx.free()
    cleanup(ctx)


def schedule_scheduler_native_task_multi_wait_test():
    my_task = None

    ctx = setup()
    sched = ctx.sched
    mem = ctx.mem

    def trap1(op, pc):
        got = my_task.wait(3)
        assert got == 1

    def trap2(op, pc):
        my_task.set_signal(1, 1)

    addr1 = ctx.machine.setup_quick_trap(trap1)
    addr2 = ctx.machine.setup_quick_trap(trap2)

    task1_ctx = MyNativeTask(ctx, set_regs={REG_D0: 42}, name="task1")
    task1 = task1_ctx.task
    my_task = task1

    # task1 setup
    pc = task1_ctx.pc
    mem.w16(pc, op_jmp)
    mem.w32(pc + 2, addr1)
    mem.w16(pc + 6, op_rts)

    task2_ctx = MyNativeTask(ctx, set_regs={REG_D0: 23}, name="task2")
    task2 = task2_ctx.task

    # task2 setup
    pc2 = task2_ctx.pc
    mem.w16(pc2, op_jmp)
    mem.w32(pc2 + 2, addr2)
    mem.w16(pc2 + 6, op_rts)

    # add task
    assert sched.add_task(task1)
    assert sched.add_task(task2)
    # run scheduler
    sched.schedule()
    assert task1.get_exit_code() == 42
    assert task2.get_exit_code() == 23

    # check that the tasks switched
    assert ctx.events == [
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.WAITING_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.WAKE_UP_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.READY_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
    ]

    task2_ctx.free()
    task1_ctx.free()
    cleanup(ctx)


# ----- Python Tasks -----


class MyPythonTask:
    def __init__(self, ctx, func, name=None, **code_kw_args):
        if name is None:
            name = "task"
        self.ctx = ctx
        self.name = name
        self.func = func
        self.stack = ctx.alloc.alloc_memory(4096, name + "_Stack")
        self.sp = self.stack.addr
        self.task = PythonTask(name, ctx.machine, self.func, self.sp)

    def free(self):
        self.ctx.alloc.free_memory(self.stack)


def schedule_scheduler_python_task_simple_test():
    ctx = setup()

    def my_func(task):
        return 42

    # add task
    task_ctx = MyPythonTask(ctx, my_func)
    task = task_ctx.task

    sched = ctx.sched
    assert sched.add_task(task)
    # run scheduler
    sched.schedule()
    exit_code = task.get_exit_code()
    assert exit_code == 42

    task_ctx.free()
    cleanup(ctx)


def schedule_scheduler_python_task_event_hook_test():
    ctx = setup()
    # set cur task callback
    sched = ctx.sched

    def my_func(task):
        return 42

    # add task
    task_ctx = MyPythonTask(ctx, my_func)
    task = task_ctx.task

    assert sched.add_task(task)
    assert sched.get_cur_task() is None
    # run scheduler
    sched.schedule()
    exit_code = task.get_exit_code()
    assert exit_code == 42

    assert ctx.events == [
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
    ]

    task_ctx.free()
    cleanup(ctx)


def schedule_scheduler_python_task_subrun_test():
    ctx = setup()
    sched = ctx.sched

    mem = ctx.mem
    pc = ctx.machine.get_scratch_begin()

    # sub run
    mem.w16(pc, op_nop)
    mem.w16(pc + 2, op_rts)

    def my_func(task):
        task.sub_run(Code(pc))
        return 42

    task_ctx = MyPythonTask(ctx, my_func)
    task = task_ctx.task

    # add task
    assert sched.add_task(task)
    # run scheduler
    sched.schedule()
    exit_code = task.get_exit_code()
    assert exit_code == 42

    assert ctx.events == [
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
    ]

    task_ctx.free()
    cleanup(ctx)


def schedule_scheduler_python_task_multi_test():
    ctx = setup(slice_cycles=30)
    sched = ctx.sched

    def task1_run(task):
        # coop multi tasking!
        task.reschedule()
        return 42

    def task2_run(task):
        # coop multi tasking!
        task.reschedule()
        return 23

    task1_ctx = MyPythonTask(ctx, task1_run, name="task1")
    task1 = task1_ctx.task
    task2_ctx = MyPythonTask(ctx, task2_run, name="task2")
    task2 = task2_ctx.task

    # add task
    assert sched.add_task(task1)
    assert sched.add_task(task2)
    # run scheduler
    sched.schedule()
    assert task1.get_exit_code() == 42
    assert task2.get_exit_code() == 23

    # check that the tasks switched
    assert ctx.events == [
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.READY_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.READY_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
    ]

    task2_ctx.free()
    task1_ctx.free()
    cleanup(ctx)


def schedule_scheduler_python_task_multi_forbid_test():
    ctx = setup(slice_cycles=30)
    sched = ctx.sched

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

    task1_ctx = MyPythonTask(ctx, task1_run, name="task1")
    task1 = task1_ctx.task
    task2_ctx = MyPythonTask(ctx, task2_run, name="task2")
    task2 = task2_ctx.task

    # add task
    assert sched.add_task(task1)
    assert sched.add_task(task2)
    # run scheduler
    sched.schedule()
    assert task1.get_exit_code() == 42
    assert task2.get_exit_code() == 23

    # check that the tasks switched
    assert ctx.events == [
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.READY_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.READY_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
    ]

    task2_ctx.free()
    task1_ctx.free()
    cleanup(ctx)


def schedule_scheduler_python_task_multi_wait_test():
    ctx = setup(slice_cycles=30)
    sched = ctx.sched

    def task1_run(task):
        got = task.wait(3)
        assert got == 1
        return 42

    def task2_run(task):
        task1.set_signal(1, 1)
        return 23

    task1_ctx = MyPythonTask(ctx, task1_run, name="task1")
    task1 = task1_ctx.task
    task2_ctx = MyPythonTask(ctx, task2_run, name="task2")
    task2 = task2_ctx.task

    # add task
    assert sched.add_task(task1)
    assert sched.add_task(task2)
    # run scheduler
    sched.schedule()
    assert task1.get_exit_code() == 42
    assert task2.get_exit_code() == 23

    # check that the tasks switched
    assert ctx.events == [
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ADD_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.WAITING_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.WAKE_UP_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.READY_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task1),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, task2),
        SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
    ]

    task2_ctx.free()
    task1_ctx.free()
    cleanup(ctx)
