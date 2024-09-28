from enum import Enum
from dataclasses import dataclass
from typing import Optional

from .regs import reg_to_str
from amitools.vamos.log import log_machine


@dataclass
class RunState:
    pc: int
    sp: int
    max_cycles: int
    nesting: int
    name: str
    cycles: int = 0
    total_cycles: int = 0
    regs: dict = None


class Runtime:
    """The Runtime allows you to run m68k code with the machine.
    Code may use traps that trigger Python code. This code may while running
    trigger nested m68k code.

    The runtime counts the cycles for the main run and nested runs.
    Whenever the cycle limit is reached then an optional callback is
    triggered. This callback may be used by a scheduler to issue a task switch.

    PyTraps that are encountered during the run are executed after the m68k
    code execution directly in the current context. I.e. any exception that
    may be raised will fall through.

    Any problem in a machine run is raised as a MachineError.

    The runtime is started with start() and either returns or throws an
    MachineError or another Python exception.
    """

    def __init__(self, machine, default_sp=None):
        self.machine = machine
        self.default_sp = default_sp
        self.max_cycle_hook = None

        self.running = False
        self.run_states = []

        self.max_cycles = 0
        self.cur_cycles = 0

    def set_max_cycle_hook(self, func):
        self.max_cycle_hook = func

    def run(
        self, pc, sp, set_regs=None, get_regs=None, max_cycles=1000, name=None
    ) -> RunState:
        """convenience method to dispatch either to start or nested_run"""
        if not self.running:
            return self.start(pc, sp, set_regs, get_regs, max_cycles, name)
        else:
            return self.nested_run(pc, sp, set_regs, get_regs, max_cycles, name)

    def start(
        self, pc, sp, set_regs=None, get_regs=None, max_cycles=1000, name=None
    ) -> RunState:
        """start the main run at given pc with stack and return result"""
        if self.running:
            raise RuntimeError("start() only allowed inside idle runtime.")

        # use stack, default stack or fail
        if not sp:
            if self.default_sp:
                sp = self.default_sp
            else:
                raise RuntimeError("start() has no valid stack!")

        # setup run state
        self.running = True
        run_state = RunState(pc, sp, max_cycles, 0, name)
        self.run_states = [run_state]

        # init cycle counting
        self.max_cycles = max_cycles
        self.cur_cycles = 0

        # execute
        log_machine.info("runtime start: %s", run_state)
        run_state.regs = self._run_loop(pc, sp, set_regs, get_regs, max_cycles)
        log_machine.info("runtime end: %s", run_state)

        # clean up run state
        self.running = False
        self.run_states = []

        return run_state

    def nested_run(
        self, pc, sp=None, set_regs=None, get_regs=None, max_cycles=0, name=None
    ) -> RunState:
        """in a PyTrap code run a nested piece of m68k code"""
        if not self.running:
            raise RuntimeError("nested_run() only allowed inside started runtime.")

        # if no own stack is given then re-use current stack
        if not sp:
            sp = self.machine.get_sp() - 4
        if max_cycles == 0:
            max_cycles = self.max_cycles

        # save CPU context
        ctx = self.machine.cpu.get_cpu_context()

        # create new run state
        nesting = len(self.run_states)
        run_state = RunState(pc, sp, max_cycles, nesting, name)
        self.run_states.append(run_state)

        # perform nested run
        log_machine.info("runtime nested start %s", run_state)
        run_state.regs = self._run_loop(pc, sp, set_regs, get_regs, max_cycles)
        log_machine.info("runtime nested end %s", run_state)

        # pop current run state
        self.run_states.pop()

        # restore CPU context
        self.machine.cpu.set_cpu_context(ctx)

        # account cycles to old run state
        old_run_state = self.run_states[-1]
        old_run_state.total_cycles += run_state.total_cycles

        return run_state

    def get_current_run_state(self):
        if len(self.run_states) > 0:
            return self.run_states[-1]

    def cycles_run(self):
        rs = self.get_current_run_state()
        if rs:
            return rs.cycles + self.machine.cycles_run()
        else:
            return 0

    def _run_loop(self, pc, sp, set_regs, get_regs, max_cycles):
        # setup pc and sp
        self.machine.prepare(pc, sp)

        # setup regs
        if set_regs:
            set_regs_txt = self._print_regs(set_regs)
            log_machine.debug("set_regs=%s", set_regs_txt)
            for reg, val in set_regs.items():
                self.machine.cpu.w_reg(reg, val)

        while True:
            # let m68k run
            er = self.machine.execute(max_cycles)

            # account cycles
            run_state = self.run_states[-1]
            run_state.cycles += er.cycles
            run_state.total_cycles += er.cycles

            # update run state pc, sp
            run_state.pc = self.machine.get_pc()
            run_state.sp = self.machine.get_sp()

            # report cycles?
            self.cur_cycles += er.cycles
            if self.cur_cycles > self.max_cycles:
                log_machine.debug(
                    "report max cycles: last=%d sum=%d (local %d, total %d)",
                    er.cycles,
                    self.cur_cycles,
                    run_state.cycles,
                    run_state.total_cycles,
                )
                # report that we reached max cycles
                if self.max_cycle_hook:
                    self.max_cycle_hook(
                        self.cur_cycles, run_state.cycles, run_state.nesting
                    )
                self.cur_cycles = 0

            # machine run has ended?
            if er.user_end:
                if run_state.pc == self.machine.get_run_exit_addr() + 2:
                    log_machine.debug("exit code reached. (%s)", er)
                    break
                else:
                    log_machine.debug("unknown user end. (%s)", er)
            # max cycles reached. report and continue
            else:
                log_machine.debug("max cycles reached: %s", er)

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
