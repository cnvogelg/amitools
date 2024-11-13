from amitools.vamos.libtypes import Process
from amitools.vamos.maptask import MappedProcess
from amitools.vamos.schedule import PythonTask, NativeTask, Code
from .stack import Stack


class DosProcess(MappedProcess):
    """Create a process that allocates all needed ressources"""

    def __init__(
        self,
        machine,
        alloc,
        name,
        stack_size=4096,
        func=None,
        seg_list=None,
        start_pc=None,
        start_regs=None,
        return_regs=None,
    ):
        # alloc stack, and task
        self.stack = Stack.alloc(alloc, stack_size, name=name + "_Stack")
        self.seg_list = seg_list
        self.proc = Process.alloc(alloc, name=name)
        self.proc.new_proc()

        sp = self.stack.get_initial_sp()
        # python task?
        if func:
            sched_task = PythonTask(name, machine, func, sp)
        else:
            if not start_pc:
                start_pc = seg_list.get_start_pc()
            # no start_regs and only D0 as return reg
            code = Code(start_pc, sp, start_regs, return_regs)
            sched_task = NativeTask(name, machine, code)

        super().__init__(sched_task, self.proc)

    def free(self):
        self.proc.free()
        self.stack.free()
        if self.seg_list:
            self.seg_list.free()

    def get_stack(self):
        return self.stack

    def get_seg_list(self):
        return self.seg_list
