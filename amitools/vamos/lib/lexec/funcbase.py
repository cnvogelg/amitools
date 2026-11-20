class FuncBase:
    def __init__(self, ctx, exec_lib):
        self.ctx = ctx
        self.exec_lib = exec_lib

    def get_my_ami_task(self):
        """return Amiga Task structure to access current task"""
        return self.ctx.task.get_ami_task()

    def get_my_sched_task(self):
        """return the scheduler task associated with current task

        the scheduler task is needed for task/signals. Returns None when no
        task is currently running (e.g. a handler is started from Python).
        """
        task = self.ctx.task
        if task is None:
            return None
        return task.get_sched_task()
