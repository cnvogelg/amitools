from amitools.vamos.libtypes import Process
from .task import MappedTask


class MappedProcess(MappedTask):
    def __init__(self, task_ctx, sched_task, ami_process=None, code=None, **kw_args):
        if not ami_process:
            name = sched_task.get_name()
            ami_process = Process.alloc(task_ctx.alloc, name=name)
            ami_process.new_proc()

        self.ami_process = ami_process
        ami_task = ami_process.task
        super().__init__(task_ctx, sched_task, ami_task=ami_task, code=code, **kw_args)

        # free process not task
        self.free_list.remove(self.ami_task)
        self.free_list.insert(0, self.ami_process)

    def is_process(self):
        return True

    def get_ami_process(self):
        return self.ami_process
