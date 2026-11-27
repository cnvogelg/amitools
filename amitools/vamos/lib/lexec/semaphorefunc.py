from amitools.vamos.libstructs import SignalSemaphoreStruct
from amitools.vamos.libtypes import List, Message
from amitools.vamos.log import log_exec
from amitools.vamos.machine.regs import REG_A0, REG_A1


class SemaphoreMixin:
    """exec.library signal semaphore LVOs (fd banner: signal semaphores)."""

    def InitSemaphore(self, ctx):
        addr = ctx.cpu.r_reg(REG_A0)
        self.semaphore_mgr.InitSemaphore(addr)
        log_exec.info("InitSemaphore(%06x)" % addr)

    def AddSemaphore(self, ctx, semaphore: SignalSemaphoreStruct):
        addr = semaphore.addr
        name = semaphore.ss_Link.ln_Name.str
        self.semaphore_mgr.AddSemaphore(addr, name)
        log_exec.info("AddSemaphore(%06x,%s)" % (addr, name))

    def RemSemaphore(self, ctx):
        addr = ctx.cpu.r_reg(REG_A1)
        self.semaphore_mgr.RemSemaphore(addr)
        log_exec.info("RemSemaphore(%06x)" % addr)

    def FindSemaphore(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_A1)
        name = ctx.mem.r_cstr(name_ptr)
        semaphore = self.semaphore_mgr.FindSemaphore(name)
        log_exec.info("FindSemaphore(%s) -> %s" % (name, semaphore))
        if semaphore is not None:
            return semaphore.addr
        else:
            return 0

    def ObtainSemaphore(self, ctx):
        self.obtain_semaphore(ctx.cpu.r_reg(REG_A0))

    def ObtainSemaphoreShared(self, ctx):
        self.obtain_semaphore(ctx.cpu.r_reg(REG_A0))

    def AttemptSemaphore(self, ctx):
        addr = ctx.cpu.r_reg(REG_A0)
        return self.attempt_semaphore(addr)

    def ReleaseSemaphore(self, ctx):
        self.release_semaphore(ctx.cpu.r_reg(REG_A0))

    # ----- semaphore lists and legacy calls -----

    def ObtainSemaphoreList(self, ctx, sigSem: List):
        """lock every semaphore in the given list."""
        for node in sigSem:
            self.obtain_semaphore(node.addr)

    def ReleaseSemaphoreList(self, ctx, sigSem: List):
        """release every semaphore in the given list."""
        for node in sigSem:
            self.release_semaphore(node.addr)

    def AttemptSemaphoreShared(self, ctx, sigSem: SignalSemaphoreStruct):
        """non-blocking shared obtain; vamos has no contention, so it wins."""
        return self.attempt_semaphore(sigSem.addr)

    def Procure(self, ctx, sigSem: SignalSemaphoreStruct, bidMsg: Message):
        """legacy (pre-V33) obtain: lock and reply the bid message."""
        self.obtain_semaphore(sigSem.addr)
        if bidMsg is not None:
            self.reply_msg(bidMsg)

    def Vacate(self, ctx, sigSem: SignalSemaphoreStruct, bidMsg: Message):
        """legacy (pre-V33) release: unlock and reply the bid message."""
        self.release_semaphore(sigSem.addr)
        if bidMsg is not None:
            self.reply_msg(bidMsg)

    # ----- internal -----

    def obtain_semaphore(self, addr):
        # nop for now: vamos does not model semaphore contention
        log_exec.info("ObtainSemaphore(%06x) ignored" % addr)

    def release_semaphore(self, addr):
        # nop for now: vamos does not model semaphore contention
        log_exec.info("ReleaseSemaphore(%06x) ignored" % addr)

    def attempt_semaphore(self, addr):
        # no contention: the lock is always available
        log_exec.info("AttemptSemaphore(%06x) -> 1" % addr)
        return 1
