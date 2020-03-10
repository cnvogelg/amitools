import sys
import traceback

from amitools.vamos.log import log_machine
from amitools.vamos.error import *
from .cpustate import CPUState


class ErrorReporter:
    def __init__(self, machine):
        self.machine = machine
        self.cpu = machine.get_cpu()
        self.mem = machine.get_mem()
        self.label_mgr = machine.get_label_mgr()

    def report_error(self, error):
        # get run nesting
        nesting = self.machine.get_run_nesting()
        log_machine.error("----- ERROR in CPU Run #%d -----", nesting)
        self._log_run_state()
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

    def _log_run_state(self):
        # get current run_state
        run_state = self.machine.get_cur_run_state()
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
