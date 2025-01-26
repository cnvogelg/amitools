from amitools.vamos.libtypes import Task


class FuncBase:
    def __init__(self, ctx, exec_lib):
        self.ctx = ctx
        self.exec_lib = exec_lib

    def get_my_task(self):
        """return Amiga Task structure to access current task"""
        ptr = self.exec_lib.this_task.aptr
        return Task(self.ctx.mem, ptr)

    def get_my_sched_task(self):
        """return the scheduler task associated with current task

        the scheduler task is needed for task/signals
        """
        return ctx.task.map_task.get_sched_task()
