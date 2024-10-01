from enum import Enum
import greenlet

from amitools.vamos.log import log_schedule
from amitools.vamos.machine import Runtime, REG_D0


class TaskState(Enum):
    TS_INVALID = 0
    TS_ADDED = 1
    TS_RUN = 2
    TS_READY = 3
    TS_WAIT = 4
    TS_EXCEPT = 5
    TS_REMOVED = 6


class TaskBase:
    """basic structure for both native and Pyhton tasks"""

    def __init__(self, name, machine):
        self.name = name
        self.machine = machine
        self.runtime = Runtime(machine)
        # state
        self.state = TaskState.TS_INVALID
        self.scheduler = None
        self.exit_code = None
        self.glet = None
        self.cpu_ctx = None

    def __repr__(self):
        return "TaskBase(%r, %s)" % (self.name, self.state)

    def config(self, scheduler, slice_cycles):
        """the scheduler configs the task"""
        self.scheduler = scheduler
        self.glet = greenlet.greenlet(self.start)

        def slice_hook(run_state):
            self.scheduler.reschedule(self)

        self.runtime.set_slice_hook(slice_cycles, slice_hook)

    def set_state(self, state):
        """the scheduler assigns a new state"""
        self.state = state

    def get_name(self):
        return self.name

    def get_run_state(self):
        """if task is running then you can get the current run state"""
        return self.runtime.get_current_run_state()

    def get_exit_code(self):
        return self.exit_code

    def reschedule(self):
        """give up this tasks execution and allow the scheduler to run another task"""
        self.scheduler.reschedule(self)

    def free(self):
        """clean up task resources, e.g. stack"""
        pass

    def start(self):
        """run the task until it ends. it might be interrupted by reschedule() calls"""
        pass

    def run(self, *args, **kw_args):
        """execute m68k code in your task"""
        return self.runtime.run(*args, **kw_args)

    def switch(self):
        self.glet.switch()

    def save_ctx(self):
        if self.runtime.is_running():
            log_schedule.debug("%s: save cpu context", self)
            self.cpu_ctx = self.machine.cpu.get_context()

    def restore_ctx(self):
        if self.runtime.is_running():
            log_schedule.debug("%s: restore cpu context", self)
            self.machine.cpu.set_context(self.cpu_ctx)


class NativeTask(TaskBase):
    """a task that runs native m68k code"""

    def __init__(
        self, name, machine, init_pc, stack, start_regs=None, return_regs=None
    ):
        super().__init__(name, machine)
        self.init_pc = init_pc
        self.stack = stack
        if start_regs is None:
            start_regs = {}
        if return_regs is None:
            return_regs = [REG_D0]
        self.start_regs = start_regs
        self.return_regs = return_regs
        self.run_state = None

    def __repr__(self):
        return (
            "NativeTask(%r, init_pc=%06x, stack=%r, start_regs=%r, return_regs=%r)"
            % (
                super().__repr__(),
                self.init_pc,
                self.stack,
                self.start_regs,
                self.return_regs,
            )
        )

    def free(self):
        if self.stack:
            self.stack.free()

    def start(self):
        pc = self.init_pc
        sp = self.get_init_sp()
        set_regs = self.start_regs
        get_regs = self.return_regs
        self.run_state = self.runtime.start(
            pc, sp, set_regs=set_regs, get_regs=get_regs
        )
        self.exit_code = self.run_state.regs[REG_D0]
        # at the end of execution remove myself
        if self.scheduler:
            self.scheduler.rem_task(self)

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

    def get_run_result(self):
        return self.run_state
