from .task import Task


class Scheduler(object):
    """handle the execution of multiple tasks"""

    def __init__(self, machine):
        self.machine = machine
        self.tasks = []
        self.cb = None
        self.main_task = None
        self.fail_task = None

    def get_machine(self):
        return self.machine

    def set_cur_task_callback(self, cb):
        self.cb = cb

    def get_num_tasks(self):
        return len(self.tasks)

    def schedule(self):
        """main work call for scheduler. at least one task must be added.
        terminates if there are no more tasks to schedule or if a task
        failed.

        return None or failed task
        """
        if self.last_task is None:
            raise RuntimeError("no task was added!")
        return self.fail_task

    def add_task(self, task):
        """add a new task and prepare for execution.

        currently the task is also executed in place here.

        returns True if task was added
        """
        self.tasks.append(task)
        self.last_task = task
        # prepare to run task
        task.prepare_run(self)
        # notify about current task
        if self.cb:
            self.cb(task)
        # let the task run
        self._execute(task, task.get_init_sp())
        # update task stack
        self.tasks.pop()
        # done run
        task.done_run(self)
        # notify about now current task
        if self.cb:
            if len(self.tasks) > 0:
                cur_task = self.tasks[-1]
            else:
                cur_task = None
            self.cb(cur_task)
        # return regs
        return True

    def rem_task(self, task):
        raise NotImplementedError

    def run_sub_task(self, sub_task):
        """run a given sub task in the context of the current task

        for now the sub task directly runs in the current task
        and returns when its finished

        returns return regs of sub task
        """
        if len(self.tasks) == 0:
            raise ValueError("no tasks are running!")
        # prepare run of sub task
        sub_task.prepare_run(self)
        # pack everything in a sub task
        stack = sub_task.stack
        if stack is None:
            init_sp = None
        else:
            init_sp = stack.get_initial_sp()
        self._execute(sub_task, init_sp)
        # done run
        sub_task.done_run(self)
        return sub_task.get_run_state().regs

    def _execute(self, task, sp):
        pc = task.get_init_pc()
        run_state = self.machine.run(
            pc,
            sp,
            set_regs=task.get_start_regs(),
            get_regs=task.get_return_regs(),
            name=task.get_name(),
        )
        task.run_state = run_state
        if run_state.error:
            # report error in schedule
            self.fail_task = task
