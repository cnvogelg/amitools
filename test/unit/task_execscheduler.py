from amitools.vamos.machine import Machine, REG_D0, op_nop, op_rts
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.task import ExecTask, ExecScheduler
from amitools.vamos.loader import SegList
from amitools.vamos.schedule import Scheduler, SchedulerEvent
from amitools.vamos.libtypes import ExecLibrary


class Ctx:
    def __init__(self):
        self.machine = Machine()
        self.alloc = MemoryAlloc.for_machine(self.machine)
        self.mem = self.machine.get_mem()
        self.scheduler = Scheduler(self.machine)
        self.exec_lib = ExecLibrary.alloc(
            self.alloc, name="exec.library", id_string="bla", neg_size=20
        )
        self.exec_lib.new()
        self.exec_scheduler = ExecScheduler(self.scheduler, self.exec_lib)

    def cleanup(self):
        self.exec_lib.free()
        assert self.alloc.is_all_free()
        self.machine.cleanup()

    def check_exec(self, this_task, task_ready, task_wait):
        assert self.exec_lib.this_task.ref == this_task
        assert self.exec_lib.task_ready.to_list(promote=True) == task_ready
        assert self.exec_lib.task_wait.to_list(promote=True) == task_wait

    def set_check_list(self, check_list):
        self.count = 0

        def event_callback(event):
            if self.count >= len(check_list):
                assert 0
            check_entry = check_list[self.count]
            print("CHECKING", check_entry, event)
            # check event
            assert check_entry[0] == event
            # check exec lib entries
            self.check_exec(*check_entry[1:])
            # next check
            self.count += 1

        self.scheduler.set_event_callback(event_callback)


def setup():
    return Ctx()


def cleanup(ctx):
    ctx.cleanup()


def add_task(ctx, name, func):
    task = ExecTask(ctx.machine, ctx.alloc, name, func=func)
    sched_task = task.get_sched_task()
    ami_task = task.get_ami_task()
    ctx.scheduler.add_task(sched_task)
    return task, sched_task, ami_task


def task_execscheduler_setup_test():
    ctx = setup()
    cleanup(ctx)


def task_execscheduler_task_simple_test():
    ctx = setup()

    def func(task):
        return 42

    task, sched_task, ami_task = add_task(ctx, "foo", func)

    ctx.set_check_list(
        [
            (
                SchedulerEvent(SchedulerEvent.Type.ADD_TASK, sched_task),
                None,
                [ami_task],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, sched_task),
                ami_task,
                [],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, sched_task),
                ami_task,
                [],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
                None,
                [],
                [],
            ),
        ]
    )

    ctx.scheduler.schedule()
    assert sched_task.get_exit_code() == 42
    task.free()
    cleanup(ctx)


def task_execscheduler_task_multi_test():
    ctx = setup()

    def func1(task):
        task.reschedule()
        return 42

    task1, sched_task1, ami_task1 = add_task(ctx, "foo", func1)

    def func2(task):
        task.reschedule()
        return 23

    task2, sched_task2, ami_task2 = add_task(ctx, "bar", func2)

    ctx.set_check_list(
        [
            (
                SchedulerEvent(SchedulerEvent.Type.ADD_TASK, sched_task1),
                None,
                [ami_task1],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ADD_TASK, sched_task2),
                None,
                [ami_task1, ami_task2],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, sched_task1),
                ami_task1,
                [ami_task2],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.READY_TASK, sched_task1),
                ami_task1,
                [ami_task1, ami_task2],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, sched_task2),
                ami_task2,
                [ami_task1],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.READY_TASK, sched_task2),
                ami_task2,
                [ami_task2, ami_task1],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, sched_task1),
                ami_task1,
                [ami_task2],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, sched_task1),
                ami_task1,
                [ami_task2],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, sched_task2),
                ami_task2,
                [],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, sched_task2),
                ami_task2,
                [],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
                None,
                [],
                [],
            ),
        ]
    )

    ctx.scheduler.schedule()
    assert sched_task1.get_exit_code() == 42
    assert sched_task2.get_exit_code() == 23
    task1.free()
    task2.free()
    cleanup(ctx)


def task_execscheduler_task_multi_wait_test():
    ctx = setup()

    def func1(task):
        got = task.wait(3)
        assert got == 1
        return 42

    task1, sched_task1, ami_task1 = add_task(ctx, "foo", func1)

    def func2(task):
        sched_task1.set_signal(1, 1)
        return 23

    task2, sched_task2, ami_task2 = add_task(ctx, "bar", func2)

    ctx.set_check_list(
        [
            (
                SchedulerEvent(SchedulerEvent.Type.ADD_TASK, sched_task1),
                None,
                [ami_task1],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ADD_TASK, sched_task2),
                None,
                [ami_task1, ami_task2],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, sched_task1),
                ami_task1,
                [ami_task2],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.WAITING_TASK, sched_task1),
                ami_task1,
                [ami_task2],
                [ami_task1],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, sched_task2),
                ami_task2,
                [],
                [ami_task1],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.WAKE_UP_TASK, sched_task1),
                ami_task2,
                [ami_task1],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.READY_TASK, sched_task2),
                ami_task2,
                [ami_task2, ami_task1],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, sched_task1),
                ami_task1,
                [ami_task2],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, sched_task1),
                ami_task1,
                [ami_task2],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, sched_task2),
                ami_task2,
                [],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.REMOVE_TASK, sched_task2),
                ami_task2,
                [],
                [],
            ),
            (
                SchedulerEvent(SchedulerEvent.Type.ACTIVE_TASK, None),
                None,
                [],
                [],
            ),
        ]
    )

    ctx.scheduler.schedule()
    assert sched_task1.get_exit_code() == 42
    assert sched_task2.get_exit_code() == 23
    task1.free()
    task2.free()
    cleanup(ctx)
