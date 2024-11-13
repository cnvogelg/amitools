from amitools.vamos.libtypes import Process
from .task import MappedTask


class MappedProcess(MappedTask):
    def __init__(self, sched_task, ami_process):
        self.ami_process = ami_process
        ami_task = ami_process.task
        super().__init__(sched_task, ami_task)

    def is_process(self):
        return True

    def get_ami_process(self):
        return self.ami_process
