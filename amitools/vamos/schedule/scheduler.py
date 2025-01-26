from enum import IntEnum
from dataclasses import dataclass
import greenlet

from amitools.vamos.log import log_schedule
from amitools.vamos.schedule.task import TaskState, TaskBase


@dataclass
class SchedulerEvent:
    class Type(IntEnum):
        ACTIVE_TASK = 0
        WAITING_TASK = 1
        ADD_TASK = 2
        REMOVE_TASK = 3
        WAKE_UP_TASK = 4
        READY_TASK = 5

    type: Type
    task: TaskBase


@dataclass
class SchedulerConfig:
    slice_cycles: int = 1000

    @classmethod
    def from_cfg(cls, schedule_cfg):
        return cls(schedule_cfg.slice_cycles)


class Scheduler(object):
    """handle the execution of multiple tasks"""

    def __init__(self, machine, config=None):
        if not config:
            config = SchedulerConfig()

        self.machine = machine
        self.config = config
        # state
        self.ready_tasks = []
        self.waiting_tasks = []
        self.event_hooks = []
        self.cur_task = None
        self.num_tasks = 0
        self.main_glet = greenlet.getcurrent()
        self.num_switch_same = 0
        self.num_switch_other = 0
        self.running = False

    @classmethod
    def from_cfg(cls, machine, schedule_cfg):
        cfg = SchedulerConfig.from_cfg(schedule_cfg)
        return cls(machine, cfg)

    def get_machine(self):
        return self.machine

    def set_event_callback(self, func):
        """the function will receive ScheduleEvent"""
        self.event_hooks.append(func)

    def get_num_tasks(self):
        """count the active tasks"""
        sum = len(self.ready_tasks) + len(self.waiting_tasks)
        if self.cur_task:
            sum += 1
        return sum

    def get_cur_task(self):
        return self.cur_task

    def schedule(self):
        """main work call for scheduler. at least one task must be added.
        terminates if there are no more tasks to schedule or if a task
        fails and an uncaught exception is thrown.
        """
        log_schedule.info("schedule(): start")

        # check that we have at least one task to run
        if len(self.ready_tasks) == 0:
            raise RuntimeError("no tasks to schedule!")

        self.running = True

        # report events for previously added tasks
        if len(self.event_hooks) > 0:
            for task in self.ready_tasks:
                self._report_event(SchedulerEvent.Type.ADD_TASK, task)

        # main loop
        while True:
            log_schedule.debug(
                "schedule: current %s",
                self.cur_task,
            )
            log_schedule.debug(
                "schedule: ready %s waiting %s",
                self.ready_tasks,
                self.waiting_tasks,
            )

            # nothing to do anymore?
            if self.get_num_tasks() == 0:
                break

            # has the current task forbid state?
            if self.cur_task and self.cur_task.is_forbidden():
                log_schedule.debug("run: keep current (forbid state)")
                task = self.cur_task
            else:
                # find a task to run
                task = self._find_run_task()
                if task is None:
                    log_schedule.error("schedule(): no task to run?!")
                    return False

            # current tasks stays the same?
            # no context switch required. simply switch to it
            if task == self.cur_task:
                self.num_switch_same += 1
                log_schedule.debug("run: current %s", task.name)
                task.keep_scheduled()
            else:
                self.num_switch_other += 1
                # switch out old
                old_task = self.cur_task
                if old_task:
                    log_schedule.debug("run: switch out %s", old_task.name)
                    # if cur task still running (not waiting)
                    # then move it to ready list
                    if old_task.get_state() == TaskState.TS_RUN:
                        old_task.set_state(TaskState.TS_READY)
                        self.ready_tasks.append(old_task)
                        # report
                        self._report_event(SchedulerEvent.Type.READY_TASK, old_task)

                    old_task.save_ctx()

                # switch in new
                self.cur_task = task
                self._make_current(task)
                task.set_state(TaskState.TS_RUN)
                log_schedule.debug("run: switch in %s", task.name)

                task.restore_ctx()

            # enter greenlet of task and resume it
            task.switch()

        # end of scheduling
        self._make_current(None)
        self.running = False

        log_schedule.info(
            "schedule(): done (switches: same=%d, other=%d)",
            self.num_switch_same,
            self.num_switch_other,
        )
        return True

    def _find_run_task(self):
        # if a ready task is available
        if len(self.ready_tasks):
            task = self.ready_tasks.pop(0)
            log_schedule.debug("take: ready task %s", task.name)
            return task

        # keep current task
        task = self.cur_task
        log_schedule.debug("take: current task %s", task.name)
        if task.get_state() in (TaskState.TS_READY, TaskState.TS_RUN):
            return task

    def _make_current(self, task):
        self.cur_task = task
        # report via event
        self._report_event(SchedulerEvent.Type.ACTIVE_TASK, task)

    def wait_task(self, task):
        """set the given task into wait state"""
        log_schedule.debug("wait_task: task %s", task.name)
        self.waiting_tasks.append(task)
        task.set_state(TaskState.TS_WAIT)
        # report via event
        self._report_event(SchedulerEvent.Type.WAITING_TASK, task)
        self.reschedule()

    def wake_up_task(self, task):
        """take task from waiting list and allow him to schedule"""
        log_schedule.debug("wake_up_task: task %s", task.name)
        self.waiting_tasks.remove(task)
        # add to front
        self.ready_tasks.insert(0, task)
        task.set_state(TaskState.TS_READY)
        # report via event
        self._report_event(SchedulerEvent.Type.WAKE_UP_TASK, task)
        # directly reschedule
        self.reschedule()

    def add_task(self, task):
        """add a new task and prepare for execution.

        returns True if task was added
        """
        self.ready_tasks.append(task)
        task.set_state(TaskState.TS_ADDED)
        # configure task
        task.config(self, self.config.slice_cycles)
        log_schedule.info("add_task: %s", task.name)
        # report via event if running or postpone it
        if self.running:
            self._report_event(SchedulerEvent.Type.ADD_TASK, task)
        return True

    def rem_task(self, task):
        # find task: is it current? removing myself...
        if self.cur_task == task:
            log_schedule.debug("rem_task: cur_task %s", task.name)
            self.cur_task = None
        # in ready list?
        elif task in self.ready_tasks:
            log_schedule.debug("rem_task: ready %s", task.name)
            self.ready_tasks.remove(task)
        # in waiting list?
        elif task in self.waiting_tasks:
            log_schedule.debug("rem_task: waiting %s", task.name)
            self.waiting_tasks.remove(task)
        # not found
        else:
            log_schedule.warning("rem_task: unknown task %s", task.name)
            return False
        # mark as removed
        task.set_state(TaskState.TS_REMOVED)
        log_schedule.info("rem_task: %s", task.name)
        # report via event if running or suppress otherwise
        if self.running:
            self._report_event(SchedulerEvent.Type.REMOVE_TASK, task)
        return True

    def _report_event(self, event, task):
        if len(self.event_hooks) > 0:
            event = SchedulerEvent(event, task)
            for hook in self.event_hooks:
                hook(event)

    def reschedule(self):
        """callback from tasks to reschedule"""
        self.main_glet.switch()

    def find_task(self, name):
        # is it the current task?
        if self.cur_task and self.cur_task.name == name:
            return self.cur_task
        # check ready list
        for task in self.ready_tasks:
            if task.name == name:
                return task
        # check wait list
        for task in self.waiting_tasks:
            if task.name == name:
                return task
