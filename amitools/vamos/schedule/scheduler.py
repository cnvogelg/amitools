import greenlet

from amitools.vamos.log import log_schedule
from amitools.vamos.schedule.task import TaskState


class Scheduler(object):
    """handle the execution of multiple tasks"""

    def __init__(self, machine, slice_cycles=1000):
        self.machine = machine
        self.slice_cycles = slice_cycles
        # state
        self.added_tasks = []
        self.ready_tasks = []
        self.waiting_tasks = []
        self.cur_task_hook = None
        self.cur_task = None
        self.num_tasks = 0
        self.main_glet = greenlet.getcurrent()
        self.num_switch_same = 0
        self.num_switch_other = 0

    @classmethod
    def from_cfg(cls, machine, schedule_cfg):
        return cls(machine, schedule_cfg.slice_cycles)

    def get_machine(self):
        return self.machine

    def set_cur_task_callback(self, func):
        self.cur_task_hook = func

    def get_num_tasks(self):
        """count the active tasks"""
        sum = len(self.ready_tasks) + len(self.waiting_tasks) + len(self.added_tasks)
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
        if len(self.added_tasks) == 0:
            raise RuntimeError("no tasks to schedule!")

        # main loop
        while True:
            log_schedule.debug(
                "schedule: current %s",
                self.cur_task,
            )
            log_schedule.debug(
                "schedule: added %s ready %s waiting %s",
                self.added_tasks,
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

        log_schedule.info(
            "schedule(): done (switches: same=%d, other=%d)",
            self.num_switch_same,
            self.num_switch_other,
        )
        return True

    def _find_run_task(self):
        # if added tasks are available take this one
        if len(self.added_tasks) > 0:
            task = self.added_tasks.pop(0)
            log_schedule.debug("take: added task %s", task.name)
            return task

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
        if self.cur_task_hook:
            self.cur_task_hook(task)

    def wait_task(self, task):
        """set the given task into wait state"""
        log_schedule.debug("wait_task: task %s", task.name)
        self.waiting_tasks.append(task)
        task.set_state(TaskState.TS_WAIT)
        self.reschedule()

    def wake_up_task(self, task):
        """take task from waiting list and allow him to schedule"""
        log_schedule.debug("wake_up_task: task %s", task.name)
        self.waiting_tasks.remove(task)
        # add to front
        self.ready_tasks.insert(0, task)
        task.set_state(TaskState.TS_READY)
        # directly reschedule
        self.reschedule()

    def add_task(self, task):
        """add a new task and prepare for execution.

        returns True if task was added
        """
        self.added_tasks.append(task)
        task.set_state(TaskState.TS_ADDED)
        # configure task
        task.config(self, self.slice_cycles)
        log_schedule.info("add_task: %s", task.name)
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
        # in added list?
        elif task in self.added_tasks:
            log_schedule.debug("rem_task: added %s", task.name)
            self.added_tasks.remove(task)
        # not found
        else:
            log_schedule.warning("rem_task: unknown task %s", task.name)
            return False
        # mark as removed
        task.set_state(TaskState.TS_REMOVED)
        log_schedule.info("rem_task: %s", task.name)
        # finally free task
        task.free()
        return True

    def reschedule(self):
        """callback from tasks to reschedule"""
        self.main_glet.switch()
