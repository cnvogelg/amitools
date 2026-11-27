from amitools.vamos.machine.regs import REG_A7


class FuncBaseMixin:
    """shared helpers for the ``exec.library`` mixins.

    The topic mixins are combined into ``ExecLibrary``, so ``self`` is the
    library implementation carrying the shared state (``ctx``, ``mem``,
    ``alloc``, ...).
    """

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

    def get_callee_pc(self, ctx):
        """a call stub log helper to extract the callee's pc"""
        sp = ctx.cpu.r_reg(REG_A7)
        return ctx.mem.r32(sp)
