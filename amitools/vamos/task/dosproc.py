from amitools.vamos.libtypes import Process
from amitools.vamos.machine import Code
from amitools.vamos.schedule import PythonTask, NativeTask
from .stack import Stack
from .exectask import ExecTask


class DosProcess(ExecTask):
    """Create a process that allocates all needed ressources"""

    def __init__(self, machine, alloc, name, **kw_args):
        # alloc
        self.proc = Process.alloc(alloc, name=name)
        self.proc.task.new_task()
        self.proc.new_proc()

        super().__init__(
            machine, alloc, name, ami_task=self.proc.task, ami_proc=self.proc, **kw_args
        )

    def free(self):
        self.proc.free()
        super().free()

    def get_current_dir(self):
        return self.proc.current_dir.aptr

    def set_current_dir(self, addr):
        self.proc.current_dir.aptr = addr

    def get_home_dir(self):
        return self.proc.home_dir.aptr

    def set_home_dir(self, addr):
        self.proc.home_dir.aptr = addr
