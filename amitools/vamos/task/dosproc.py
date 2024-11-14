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
        self.proc.new_proc()

        super().__init__(machine, alloc, name, ami_task=self.proc.task, **kw_args)

    def free(self):
        self.proc.free()
        super().free()
