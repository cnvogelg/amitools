class Scheduler(object):
    """handle the execution of multiple tasks"""

    def __init__(self, machine):
        self.machine = machine
        self.tasks = []
        self.cur_task_hook = None
        self.cur_task = None

    def get_machine(self):
        return self.machine

    def set_cur_task_callback(self, func):
        self.cur_task_hook = func

    def get_num_tasks(self):
        return len(self.tasks)

    def get_cur_task(self):
        return self.cur_task

    def schedule(self):
        """main work call for scheduler. at least one task must be added.
        terminates if there are no more tasks to schedule or if a task
        failed.

        return result of last task
        """
        # check that we have at least one task to run
        if len(self.tasks) == 0:
            raise RuntimeError("no tasks to schedule!")

        # currently we are single task
        # so for now simply run a single task
        task = self.tasks[0]

        # report this task
        self.cur_task = task
        if self.cur_task_hook:
            self.cur_task_hook(task)

        # start task
        task.start()

        # cleanup task
        task.free()

        # no more cur task
        self.cur_task = None
        if self.cur_task_hook:
            self.cur_task_hook(None)

    def add_task(self, task):
        """add a new task and prepare for execution.

        returns True if task was added
        """
        self.tasks.append(task)
        # assign myself
        task.set_scheduler(self)
        # return regs
        return True

    def rem_task(self, task):
        raise NotImplementedError

    def reschedule(self, task):
        """callback from tasks to reschedule"""
        pass
