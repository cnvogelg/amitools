from amitools.vamos.machine.regs import *


class Task(object):
    """describe a unit of execution for the scheduler"""

    def __init__(self, name, init_pc, stack, start_regs=None, return_regs=None):
        self.name = name
        self.init_pc = init_pc
        self.stack = stack
        if start_regs is None:
            start_regs = {}
        if return_regs is None:
            return_regs = [REG_D0]
        self.start_regs = start_regs
        self.return_regs = return_regs
        self.run_state = None

    def prepare_run(self, sched):
        pass

    def done_run(self, sched):
        if self.stack:
            self.stack.free()

    def __repr__(self):
        return "Task(%r, init_pc=%06x, stack=%r, start_regs=%r, return_regs=%r)" % (
            self.name,
            self.init_pc,
            self.stack,
            self.start_regs,
            self.return_regs,
        )

    def get_name(self):
        return self.name

    def get_init_pc(self):
        return self.init_pc

    def get_stack(self):
        return self.stack

    def get_init_sp(self):
        return self.stack.get_initial_sp()

    def get_start_regs(self):
        return self.start_regs

    def get_return_regs(self):
        return self.return_regs

    def get_run_state(self):
        return self.run_state

    def get_result_regs(self):
        return self.run_state.regs
