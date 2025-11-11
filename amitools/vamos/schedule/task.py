from enum import Enum
import greenlet

from amitools.vamos.log import log_schedule
from amitools.vamos.machine import Runtime, REG_D0


class TaskStop(Exception):
    pass


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
        self.state_hook = None
        self.sigmask_hook = None
        # state
        self.state = TaskState.TS_INVALID
        self.scheduler = None
        self.exit_code = None
        self.error = None
        self.stopped = False
        self.glet = None
        self.cpu_ctx = None
        self.forbid_cnt = 0
        self.forbid_reschedule = False
        self.sigmask_wait = 0
        self.sigmask_received = 0

    def __repr__(self):
        return "TaskBase(%r, %s)" % (self.name, self.state)

    def config(self, scheduler, slice_cycles):
        """the scheduler configs the task"""
        self.scheduler = scheduler
        self.glet = greenlet.greenlet(self.start)

        def slice_hook(run_state):
            self.scheduler.reschedule()

        self.runtime.set_slice_hook(slice_cycles, slice_hook)

    def set_state_callback(self, hook):
        self.state_hook = hook

    def set_sigmask_callback(self, hook):
        self.sigmask_hook = hook

    def set_state(self, state):
        """the scheduler assigns a new state"""
        self.state = state
        # call hook
        if self.state_hook:
            self.state_hook(self, state)

    def get_state(self):
        return self.state

    def get_name(self):
        return self.name

    def get_start_sp(self):
        return None

    def get_code(self):
        return None

    def get_run_state(self):
        """if task is running then you can get the current run state"""
        return self.runtime.get_current_run_state()

    def get_run_result(self):
        return None

    def get_exit_code(self):
        """if the task exited without error then return the error code"""
        return self.exit_code

    def get_error(self):
        """if task failed then return MachineError here"""
        return self.error

    def was_stopped(self):
        """return True if task was stopped"""
        return self.stopped

    def reschedule(self):
        """give up this tasks execution and allow the scheduler to run another task"""
        self.scheduler.reschedule()

    def forbid(self):
        """do not switch away from my task until permit() is called"""
        self.forbid_cnt += 1
        log_schedule.debug("%s: forbid (cnt=%d)", self.name, self.forbid_cnt)
        return self.forbid_cnt

    def permit(self):
        """re-enable task switching"""
        self.forbid_cnt -= 1
        log_schedule.debug("%s: permit (cnt=%d)", self.name, self.forbid_cnt)
        if self.forbid_cnt == 0:
            # if a schedule was triggered during the forbid state then reschedule
            if self.forbid_reschedule:
                self.forbid_reschedule = 0
                self.reschedule()
        return self.forbid_cnt

    def is_forbidden(self):
        return self.forbid_cnt > 0

    def keep_scheduled(self):
        """notified by scheduler that the task stays scheduled"""
        if self.forbid_cnt > 0:
            # set a flag that we scheduled and kept the task
            self.forbid_reschedule = True

    def wait(self, sigmask):
        """suspend the task in wait state"""
        # there are already matching signals set
        # return without waiting
        got_mask = self.sigmask_received & sigmask
        if got_mask != 0:
            return got_mask

        # set our wait mask
        self.sigmask_wait = sigmask
        self._sync_sigmask()

        # go waiting. reschedule
        log_schedule.debug("%s: enter wait", self.name)
        self.scheduler.wait_task(self)

        # we will return here if we were removed from waiting list
        # and our got mask is not empty anymore
        got_mask = self.sigmask_received & sigmask
        log_schedule.debug("%s: leave wait. got_mask=%x", self.name, got_mask)

        # now reset wait mask
        self.sigmask_wait = 0
        self._sync_sigmask()

        return got_mask

    def get_signal(self):
        return self.sigmask_received

    def set_signal(self, new_signals, sigmask):
        """set some of our signals"""
        log_schedule.debug("%s: set_signal(%x, %x)", self.name, new_signals, sigmask)
        old_mask = self.sigmask_received
        self.sigmask_received = new_signals | (self.sigmask_received & ~sigmask)
        self._sync_sigmask()
        # check if task is waiting for some of the signals
        if self.sigmask_wait != 0:
            got_mask = self.sigmask_received & self.sigmask_wait
            if got_mask != 0:
                log_schedule.debug("%s: set_signal -> wake me up", self.name)
                self.scheduler.wake_up_task(self)
        # return current mask
        log_schedule.debug(
            "%s: set_signal old=%08x -> sigmask=%08x",
            self.name,
            old_mask,
            self.sigmask_received,
        )
        return old_mask

    def _sync_sigmask(self):
        if self.sigmask_hook:
            self.sigmask_hook(self, self.sigmask_received, self.sigmask_wait)

    def start(self):
        """run the task until it ends. it might be interrupted by reschedule() calls"""
        pass

    def stop(self):
        """stop a running task by throwing a TaskEnd exception"""
        log_schedule.debug("%s: stop!", self.name)
        self.glet.throw(TaskStop())

    def sub_run(self, code, name=None):
        """execute m68k code in your task"""
        # inject own stack if needed
        if not self.runtime.is_running():
            if not code.sp:
                code.sp = self.get_start_sp()
                assert code.sp is not None
        return self.runtime.run(code, name=name)

    def switch(self):
        self.glet.switch()

    def save_ctx(self):
        if self.runtime.is_running():
            log_schedule.debug("%s: save cpu context", self.name)
            self.cpu_ctx = self.machine.cpu.get_cpu_context()

    def restore_ctx(self):
        if self.runtime.is_running():
            log_schedule.debug("%s: restore cpu context", self.name)
            self.machine.cpu.set_cpu_context(self.cpu_ctx)

    def find_task(self, name):
        return self.scheduler.find_task(name)

    def find_task_pred_func(self, pred_func):
        return self.scheduler.find_task_pred_func(pred_func)


class NativeTask(TaskBase):
    """a task that runs native m68k code"""

    def __init__(self, name, machine, code):
        super().__init__(name, machine)
        self.code = code
        self.run_state = None

    def __repr__(self):
        return "NativeTask(%s, code=%r)" % (
            super().__repr__(),
            self.code,
        )

    def start(self):
        """start task

        setup regs, exec native code via runtime, rem task
        return exit code or MachineError if failed
        """
        # ensure REG_D0 in result
        get_regs = self.code.get_regs
        if get_regs is None:
            self.code.get_regs = [REG_D0]
        elif REG_D0 not in get_regs:
            self.code.get_regs.append(REG_D0)

        log_schedule.debug("%s: start native code %r", self.name, self.code)
        try:
            self.run_state = self.runtime.start(self.code)
        except TaskStop:
            log_schedule.debug("%s: task stop received!")
            self.run_state = None

        # at the end of execution remove myself
        if self.scheduler:
            self.scheduler.terminate_task(self)

        if self.run_state:
            # pick up potential machine error
            mach_error = self.run_state.mach_error
            if mach_error:
                log_schedule.debug(
                    "%s: done native code. mach error=%s", self.name, mach_error
                )
                self.error = mach_error
                return mach_error
            else:
                # regular termination of task -> error code in D0
                self.exit_code = self.run_state.regs[REG_D0] & 0xFF
                log_schedule.debug(
                    "%s: done native code. exit_code=%d", self.name, self.exit_code
                )
                return self.exit_code
        else:
            # task was stopped
            log_schedule.debug("%s: done native code. stopped!", self.name)
            self.stopped = True
            return None

    def get_start_pc(self):
        return self.code.pc

    def get_start_sp(self):
        return self.cod.sp

    def get_code(self):
        return self.code

    def get_run_result(self):
        return self.run_state

    def get_return_regs(self):
        return self.run_state.regs


class PythonTask(TaskBase):
    """a task running Python code that may use 68k code in sub runs"""

    def __init__(self, name, machine, run_func=None, start_sp=None):
        """either supply a run function and
        an optional own stack ptr if you want to run m68k code"""
        super().__init__(name, machine)
        self.run_func = run_func
        self.start_sp = start_sp

    def __repr__(self):
        return "VamosTask(%s, run_func=%r, start_sp=%r)" % (
            super().__repr__(),
            self.run_func,
            self.start_sp,
        )

    def run(self):
        """overload your own code here"""
        return 0

    def get_start_sp(self):
        return self.start_sp

    def start(self):
        # either run run() func or method
        log_schedule.debug("%s: start Python code", self.name)

        try:
            if self.run_func:
                self.exit_code = self.run_func(self)
            else:
                self.exit_code = self.run()
        except TaskStop:
            log_schedule.debug("%s: Python task stop received!", self.name)

        log_schedule.debug(
            "%s: done Python code. exit_code=%d", self.name, self.exit_code
        )
        # at the end of execution remove myself
        if self.scheduler:
            self.scheduler.terminate_task(self)
        return self.exit_code
