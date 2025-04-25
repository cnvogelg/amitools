import sys
import traceback

from amitools.vamos.log import log_machine
from amitools.vamos.error import VamosError
from .cpustate import CPUState


class MachineError(VamosError):
    def __init__(self, pc, sp):
        self.pc = pc
        self.sp = sp

    def __str__(self):
        return f"Machine Error (pc={self.pc}, sp={self.sp})"


class InvalidMemoryAccessError(MachineError):
    def __init__(self, pc, sp, mode, width, addr):
        super().__init__(pc, sp)
        self.mode = mode
        self.width = width
        self.addr = addr

    def __str__(self):
        return "Invalid Memory Access (pc=%06x, sp=%06x) %s(%d) @%06x" % (
            self.pc,
            self.sp,
            self.mode,
            2**self.width,
            self.addr,
        )


class CPUHWExceptionError(MachineError):
    def __init__(self, pc, sp, sr, exc_num):
        super().__init__(pc, sp)
        self.sr = sr
        self.exc_num = exc_num

    def __str__(self):
        return "CPU HW (pc=%06x, sp=%06x) sr=%04x exc_num=%02x" % (
            self.pc,
            self.sp,
            self.sr,
            self.exc_num,
        )


class ResetOpcodeError(MachineError):
    def __init__(self, pc, sp):
        super().__init__(pc, sp)

    def __str__(self):
        return f"Reset Opcode (pc={self.pc}, sp={self.sp})"


class ErrorReporter:
    def __init__(self, runtime):
        self.runtime = runtime
        self.machine = runtime.machine
        self.cpu = self.machine.get_cpu()
        self.mem = self.machine.get_mem()
        self.label_mgr = self.machine.get_label_mgr()

    def report_error(self, error):
        run_state = self.runtime.get_current_run_state()
        log_machine.error("----- ERROR in CPU Run #%d -----", run_state.nesting)
        self._log_run_state(run_state)
        self._log_mem_info(error)
        self._log_cpu_state()
        self._log_exc(error)

    def _log_exc(self, error):
        # show traceback if exception is pending
        if sys.exc_info()[0]:
            lines = traceback.format_exc().split("\n")
            for line in lines:
                if line != "":
                    log_machine.error(line)
        else:
            etype = error.__class__.__name__
            log_machine.error("%s: %s", etype, error)

    def _log_run_state(self, run_state):
        # get current run_state
        log_machine.error(
            "Run: '%s': Initial PC=%06x, SP=%06x",
            run_state.name,
            run_state.pc,
            run_state.sp,
        )

    def _log_mem_info(self, error):
        # memory error?
        if isinstance(error, InvalidMemoryAccessError):
            addr = error.addr
            if self.label_mgr:
                label, offset = self.label_mgr.get_label_offset(addr)
            else:
                label, offset = None, 0
            if label is not None:
                log_machine.error("@%08x -> +%06x %s", addr, offset, label)

    def _log_cpu_state(self):
        # give CPU state dump
        cpu_state = CPUState()
        cpu_state.get(self.cpu)
        pc = cpu_state.pc
        if self.label_mgr:
            label, offset = self.label_mgr.get_label_offset(pc)
        else:
            label, offset = None, 0
        if label is not None:
            log_machine.error("PC=%08x -> +%06x %s", pc, offset, label)
        for d in cpu_state.dump():
            log_machine.error(d)
        # stack range dump
        sp = cpu_state.ax[7]
        self._log_stack(sp)

    def _log_stack(self, sp):
        ram_total = self.machine.get_ram_total()
        vals = []
        for x in range(-32, 32, 4):
            addr = sp + x
            if addr >= 0 and addr < ram_total:
                val = self.mem.r32(sp + x)
                vals.append("SP%+03d=%06x" % (x, val))
            else:
                vals.append("SP%+03d=------" % x)
        log_machine.error(" ".join(vals[0:8]))
        log_machine.error(" ".join(vals[8:]))
