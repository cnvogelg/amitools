from dataclasses import dataclass

from .regs import reg_to_str
from .error import MachineError, ErrorReporter
from amitools.vamos.log import log_machine


@dataclass
class RunState:
    pc: int
    sp: int
    nesting: int
    name: str
    cycles: int = 0
    total_cycles: int = 0
    slice_cycles: int = 0
    exit: bool = False
    regs: dict = None
    mach_error: MachineError = None
    mach_error_run_state = None


@dataclass
class Code:
    pc: int
    sp: int = None
    set_regs: dict = None
    get_regs: dict = None


class Runtime:
    """The Runtime allows you to run m68k code with the machine.
    Code may use traps that trigger Python code. This code may while running
    trigger nested m68k code.

    The runtime counts the cycles for the main run and nested runs.
    Whenever the slice cycle limit is reached then an optional callback is
    triggered. This callback may be used by a scheduler to issue a task switch.

    PyTraps that are encountered during the run are executed after the m68k
    code execution directly in the current context. I.e. any exception that
    may be raised will fall through.

    Any problem (hw error) in a machine run is returned as a MachineError
    in RunState.mach_error.

    The runtime is started with start() and either returns a RunState
    or another Python exception.
    """

    def __init__(self, machine, run_cycles=1000, default_sp=None):
        self.machine = machine
        self.default_sp = default_sp

        self.slice_hook = None
        self.slice_cycles = 0

        self.running = False
        self.run_states = []

        self.run_cycles = run_cycles
        self.left_cycles = 0

    def set_slice_hook(self, slice_cycles, func):
        """setup slice hook to get a callback after slice cycles"""
        self.slice_cycles = slice_cycles
        self.slice_hook = func

    def reset_slice(self):
        """allow to reset slice reporting"""
        self.left_cycles = self.slice_cycles

    def is_running(self):
        return self.running

    def run(self, code: Code, name: str = None) -> RunState:
        """convenience method to dispatch either to start or nested_run"""
        if not self.running:
            return self.start(code, name)
        else:
            return self.nested_run(code, name)

    def start(self, code: Code, name: str = None) -> RunState:
        """start the main run at given pc with stack and return result"""
        if self.running:
            raise RuntimeError("start() only allowed inside idle runtime.")

        # use stack, default stack or fail
        sp = code.sp
        if not sp:
            if self.default_sp:
                sp = self.default_sp
            else:
                raise RuntimeError("start() has no valid stack!")

        # setup run state
        self.running = True
        run_state = RunState(code.pc, sp, 0, name)
        self.run_states = [run_state]

        # init cycle counting for slice hook
        self.left_cycles = self.slice_cycles

        # execute
        try:
            log_machine.info("runtime start: %s", run_state)
            run_state.regs = self._run_loop(run_state, code.set_regs, code.get_regs)
            log_machine.info("runtime end: %s", run_state)
        except MachineError as me:
            run_state.mach_error = me
            run_state.mach_error_run_state = run_state
            er = ErrorReporter(self.machine)
            er.report_error(me)

        # clean up run state
        self.running = False
        self.run_states = []

        return run_state

    def nested_run(self, code: Code, name=None) -> RunState:
        """in a PyTrap code run a nested piece of m68k code"""
        if not self.running:
            raise RuntimeError("nested_run() only allowed inside started runtime.")

        # if no own stack is given then re-use current stack
        sp = code.sp
        if not sp:
            sp = self.machine.get_sp() - 4

        # save CPU context
        ctx = self.machine.cpu.get_cpu_context()

        # get old run state and take cycles
        old_run_state = self.run_states[-1]
        old_total = old_run_state.total_cycles

        # calc current slice cycles
        slice_cycles = self.slice_cycles - self.left_cycles

        # create new run state
        nesting = len(self.run_states)
        run_state = RunState(
            code.pc,
            sp,
            nesting,
            name,
            total_cycles=old_total,
            slice_cycles=slice_cycles,
        )
        self.run_states.append(run_state)

        # perform nested run
        try:
            log_machine.info("runtime nested start %s", run_state)
            run_state.regs = self._run_loop(run_state, code.set_regs, code.get_regs)
            log_machine.info("runtime nested end %s", run_state)
        except MachineError as me:
            run_state.mach_error = me
            run_state.mach_error_run_state = run_state
            er = ErrorReporter(self.machine)
            er.report_error(me)

        # pop current run state
        self.run_states.pop()

        # restore CPU context
        self.machine.cpu.set_cpu_context(ctx)

        # take over total cycles
        old_run_state.total_cycles = run_state.total_cycles

        # propagate machine error
        old_run_state.mach_error = run_state.mach_error

        return run_state

    def get_current_run_state(self):
        if len(self.run_states) > 0:
            return self.run_states[-1]

    def _run_loop(self, run_state, set_regs, get_regs):
        # setup pc and sp
        self.machine.prepare(run_state.pc, run_state.sp)

        # setup regs
        if set_regs:
            set_regs_txt = self._print_regs(set_regs)
            log_machine.debug("set_regs=%s", set_regs_txt)
            for reg, val in set_regs.items():
                self.machine.cpu.w_reg(reg, val)

        while True:
            # are we handling slices?
            if self.slice_cycles > 0:
                # nothing left? report
                if self.left_cycles <= 0:
                    log_machine.debug("report slice cycles: %s", run_state)
                    # report that we reached max cycles
                    if self.slice_hook:
                        self.slice_hook(run_state)
                    # reset slice cycles
                    self.left_cycles = self.slice_cycles
                # slice runs use the left cycles
                run_cycles = self.left_cycles
            else:
                # non-slice runs use run_cycles
                run_cycles = self.run_cycles

            # let m68k run
            er = self.machine.execute(run_cycles)

            # account cycles
            run_state.cycles += er.cycles
            run_state.total_cycles += er.cycles
            if self.left_cycles > 0:
                self.left_cycles -= er.cycles
                run_state.slice_cycles = self.slice_cycles - self.left_cycles

            # update run state pc, sp
            run_state.pc = self.machine.get_pc()
            run_state.sp = self.machine.get_sp()

            # machine run has ended?
            if self.machine.was_exit(er):
                run_state.exit = True
                log_machine.debug("exit code reached. (%s)", er)
                break
            # run cycles reached. report and continue
            else:
                log_machine.debug("run cycles reached: %s", er)

        # return regs?
        if get_regs:
            regs = {}
            for reg in get_regs:
                val = self.machine.cpu.r_reg(reg)
                regs[reg] = val
            regs_text = self._print_regs(regs)
            log_machine.debug("get_regs=%s", regs_text)
            return regs

    def _print_regs(self, regs):
        res = {}
        for r in regs:
            v = regs[r]
            key = reg_to_str[r]
            val = "%06x" % v
            res[key] = val
        return res
