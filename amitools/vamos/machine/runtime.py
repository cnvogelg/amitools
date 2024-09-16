from enum import Enum
from dataclasses import dataclass
from typing import Optional

from .machine import ExecutionStatus, ExecutionResult
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

    def __init__(self, machine):
        self.machine = machine
        self.max_cycle_hook = None

        self.running = False
        self.run_states = None

        self.max_cycles = 0
        self.cur_cycles = 0
        self.total_cycles = 0

    def set_max_cycle_hook(self, func):
        self.max_cycle_hook = func

    def run(self, pc, sp, set_regs=None, get_regs=None, max_cycles=1000, name=None):
        """convenience method to dispatch either to start or nested_run"""
        if not self.running:
            return self.start(pc, sp, set_regs, get_regs, max_cycles, name)
        else:
            return self.nested_run(pc, sp, set_regs, get_regs, max_cycles, name)

    def start(self, pc, sp, set_regs=None, get_regs=None, max_cycles=1000, name=None):
        """start the main run at given pc with stack and return result"""
        if self.running:
            raise RuntimeError("start() only allowed inside idle runtime.")

        self.running = True
        run_state = RunState(pc, sp, max_cycles, 0, name)
        self.run_states = [run_state]

        self.max_cycles = max_cycles
        self.cur_cycles = 0
        self.total_cycles = 0
        log_machine.info("runtime start: %s", run_state)

        regs = self._run_loop(pc, sp, set_regs, get_regs, max_cycles)

        self.running = False
        pc = self.machine.get_pc()
        sp = self.machine.get_sp()
        log_machine.info(
            "runtime end: pc=%x sp=%x (cycles local=%d, total=%d)",
            pc,
            sp,
            run_state.cycles,
            self.total_cycles,
        )
        return regs

    def nested_run(
        self, pc, sp=None, set_regs=None, get_regs=None, max_cycles=0, name=None
    ):
        """in a PyTrap code run a nested piece of m68k code"""
        if not self.running:
            raise RuntimeError("nested_run() only allowed inside started runtime.")

        # if no own stack is given then re-use current stack
        if not sp:
            sp = self.machine.get_sp() - 4
        if max_cycles == 0:
            max_cycles = self.max_cycles

        # reset local cycles

        # create new run state
        nesting = len(self.run_states)
        run_state = RunState(pc, sp, max_cycles, nesting, name)
        self.run_states.append(run_state)

        log_machine.info("runtime nested_run: %s", run_state)

        # perform nested run
        regs = self._run_loop(pc, sp, set_regs, get_regs, max_cycles)

        # pop run state
        self.run_states.pop()

        pc = self.machine.get_pc()
        sp = self.machine.get_sp()
        log_machine.info(
            "runtime nested_run: #%d done pc=%x sp=%x (cycles local=%d, total=%d)",
            len(self.run_states),
            pc,
            sp,
            run_state.cycles,
            self.total_cycles,
        )
        return regs

    def get_current_run_state(self):
        if self.running:
            return self.run_states[-1]

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
            rs = self.machine.execute(max_cycles)

            # account cycles
            cycles = rs.cycles
            self.total_cycles += cycles
            run_state = self.run_states[-1]
            run_state.cycles += cycles

            # report cycles?
            self.cur_cycles += cycles
            if self.cur_cycles > self.max_cycles:
                log_machine.debug(
                    "report max cycles: this=%d %d (local %d, total %d)",
                    cycles,
                    self.cur_cycles,
                    run_state.cycles,
                    self.total_cycles,
                )
                # report that we reached max cycles
                if self.max_cycle_hook:
                    self.max_cycle_hook(
                        self.cur_cycles, run_state.cycles, run_state.nesting
                    )
                self.cur_cycles = 0

            # max cycles reached. report and continue
            if rs.status == ExecutionStatus.MAX_CYCLES:
                log_machine.debug("max cycles reached: %d", cycles)
            # trap encountered. call and continue
            elif rs.status == ExecutionStatus.TRAP:
                log_machine.debug("calling trap: %r (cycles %d)", rs.trap, cycles)
                rs.trap.call()
                log_machine.debug("trap done")
            # done. main code ended
            elif rs.status == ExecutionStatus.EXIT_CODE:
                log_machine.debug("exit code reached. (cycles %d)", cycles)
                break
            # raise error
            elif rs.status == ExecutionStatus.ERROR:
                raise rs.error

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
