from amitools.vamos.log import log_exec
from amitools.vamos.machine.regs import REG_D0

from .funcbase import FuncBaseMixin
from .supervisor import run_supervisor


class MiscMixin(FuncBaseMixin):
    """exec.library misc LVOs (fd banner: misc/diagnostics)."""

    def Supervisor(self, ctx):
        return run_supervisor(ctx)

    def Alert(self, ctx, code):
        log_exec.error("ALERT: code=%08x", code)

    def Debug(self, ctx, flags):
        # vamos has no debugger to drop into
        log_exec.info("Debug(flags=%08x) ignored: no debugger", flags)

    def GetCC(self, ctx):
        # the condition codes are the low byte of the status register.
        # return them in D0 without touching the SR.
        cc = ctx.cpu.r_sr() & 0xFF
        ctx.cpu.w_reg(REG_D0, cc)
        log_exec.info("GetCC() -> %04x", cc)

    def ColdReboot(self, ctx):
        # a real cold reboot resets the whole machine: vamos has no clean
        # path to restart the emulation from an LVO, so keep it a stub
        log_exec.warning("ColdReboot() ignored: vamos cannot reboot the machine")

    def SumKickData(self, ctx):
        # no Kickstart ROM is present in vamos
        log_exec.info("SumKickData() -> 0: no Kickstart ROM")
        return 0

    def ObtainQuickVector(self, ctx, interruptCode):
        """install a quick interrupt vector.

        vamos has no VBR/quick vectors, so like AROS this returns 0 and the
        caller must fall back to a normal interrupt server.
        """
        log_exec.info("ObtainQuickVector(%08x) -> 0: no quick vectors", interruptCode)
        return 0

    def ChildFree(self, ctx, tid):
        # vamos has no task/process child registry
        log_exec.warning("ChildFree(tid=%d) ignored: no child registry", tid)
        return 0

    def ChildOrphan(self, ctx, tid):
        log_exec.warning("ChildOrphan(tid=%d) ignored: no child registry", tid)
        return 0

    def ChildStatus(self, ctx, tid):
        log_exec.warning("ChildStatus(tid=%d) ignored: no child registry", tid)
        return 0

    def ChildWait(self, ctx, tid):
        log_exec.warning("ChildWait(tid=%d) ignored: no child registry", tid)
        return 0
