"""Exec software interrupts: Cause() and PA_SOFTINT message ports.

Exec queues a caused interrupt on one of five SoftIntList priority queues and
raises the software interrupt request, so when called from a task the
interrupt is served before Cause() returns. vamos has no interrupt levels:
the handler runs as a nested 68k call on the caller's stack, with is_Data in
A1, is_Code in A5 and ExecBase in A6. The caller's registers are restored
afterwards.

Software interrupts do not nest: one caused while another one runs (e.g. a
handler that PutMsg()s to a PA_SOFTINT port) is queued and served when the
running one returns, in priority order, as exec does.
"""

from amitools.vamos.log import log_exec
from amitools.vamos.machine import REG_A1, REG_A5, REG_A6, Code
from amitools.vamos.libstructs import InterruptStruct, NodeStruct, NodeType


def _offset(struct, name):
    return struct.sdef.find_field_def_by_name(name).offset


_LN_TYPE = _offset(InterruptStruct, "is_Node") + _offset(NodeStruct, "ln_Type")
_LN_PRI = _offset(InterruptStruct, "is_Node") + _offset(NodeStruct, "ln_Pri")
_IS_DATA = _offset(InterruptStruct, "is_Data")
_IS_CODE = _offset(InterruptStruct, "is_Code")


class SoftIntFunc:
    def __init__(self, ctx, exec_base_addr):
        self.ctx = ctx
        self.exec_base_addr = exec_base_addr
        # caused interrupts not served yet, highest priority first
        self._pending = []
        self._serving = False

    def cause(self, intr_addr):
        """Cause(interrupt): run the interrupt's code with is_Data in A1."""
        if not intr_addr:
            log_exec.warning("Cause: NULL interrupt")
            return
        mem = self.ctx.mem
        # exec marks a queued interrupt NT_SOFTINT and ignores it until served
        if mem.r8(intr_addr + _LN_TYPE) == NodeType.NT_SOFTINT:
            log_exec.debug("Cause(%06x): already pending", intr_addr)
            return
        mem.w8(intr_addr + _LN_TYPE, NodeType.NT_SOFTINT)
        self._enqueue(intr_addr)
        if self._serving:
            log_exec.debug("Cause(%06x): queued behind running interrupt", intr_addr)
            return
        self._serving = True
        try:
            while self._pending:
                self._serve(self._pending.pop(0))
        finally:
            self._serving = False

    def _enqueue(self, intr_addr):
        # exec keeps five queues (-32, -16, 0, 16, 32); within a queue it is
        # first in, first out
        pri = self._pri_class(intr_addr)
        pos = len(self._pending)
        for i, other in enumerate(self._pending):
            if self._pri_class(other) < pri:
                pos = i
                break
        self._pending.insert(pos, intr_addr)

    def _pri_class(self, intr_addr):
        pri = self.ctx.mem.r8s(intr_addr + _LN_PRI)
        # -32..-17, -16..-1, 0..15, 16..31, 32..
        return max(-2, min(2, pri // 16))

    def _serve(self, intr_addr):
        mem = self.ctx.mem
        # exec removes the node and marks it NT_INTERRUPT before calling it,
        # so the handler may Cause() it again
        mem.w8(intr_addr + _LN_TYPE, NodeType.NT_INTERRUPT)
        code = mem.r32(intr_addr + _IS_CODE)
        data = mem.r32(intr_addr + _IS_DATA)
        if code == 0:
            log_exec.warning("Cause(%06x): is_Code is NULL", intr_addr)
            return
        log_exec.info("Cause(%06x): code=%06x data=%06x", intr_addr, code, data)
        set_regs = {REG_A1: data, REG_A5: code, REG_A6: self.exec_base_addr}
        result = self.ctx.runner(Code(code, set_regs=set_regs), name="SoftInt")
        if result.mach_error:
            raise result.mach_error
