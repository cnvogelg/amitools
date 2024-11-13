from amitools.vamos.libtypes import Task
from amitools.vamos.maptask import MappedTask
from amitools.vamos.machine import Code
from amitools.vamos.schedule import PythonTask, NativeTask
from .stack import Stack


class ExecTask(MappedTask):
    """Create a task that allocates all needed ressources"""

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
        self.task = Task.alloc(alloc, name=name)
        self.task.new_task()

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

        super().__init__(sched_task, self.task)

    def free(self):
        self.task.free()
        self.stack.free()
        if self.seg_list:
            self.seg_list.free()

    def get_stack(self):
        return self.stack

    def get_seg_list(self):
        return self.seg_list
