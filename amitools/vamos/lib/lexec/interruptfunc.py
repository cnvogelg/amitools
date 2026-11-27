from amitools.vamos.libstructs import InterruptStruct
from amitools.vamos.log import log_exec
from amitools.vamos.machine.regs import REG_D0

from .funcbase import FuncBaseMixin


class InterruptMixin(FuncBaseMixin):
    """exec.library interrupt-control LVOs (fd banner: interrupts)."""

    def Disable(self, ctx):
        # map disable to forbid for now
        # (since we do not deal with irqs right now)
        log_exec.info("Disable -> Forbid")
        self.forbid()

    def Enable(self, ctx):
        # map enable to permit for now
        # (since we do not deal with irqs right now)
        log_exec.info("Enable -> Permit")
        self.permit()

    def Forbid(self, ctx):
        self.forbid()

    def Permit(self, ctx):
        self.permit()

    def Cause(self, ctx, interrupt):
        self.soft_int.cause(interrupt)

    # ----- status register / supervisor mode (RKRM) -----

    def SetSR(self, ctx, newSR, mask):
        cpu = ctx.cpu
        old_sr = cpu.r_sr()
        new_sr = (old_sr & ~mask) | (newSR & mask)
        cpu.w_sr(new_sr & 0xFFFF)
        # return the old SR in D0. Write D0 directly and return None so the
        # call stub does not recompute the condition codes from the result.
        cpu.w_reg(REG_D0, old_sr)
        log_exec.info(
            "SetSR: newSR=%08x mask=%08x -> old=%04x new=%04x",
            newSR,
            mask,
            old_sr,
            new_sr & 0xFFFF,
        )

    def SuperState(self, ctx):
        """enter supervisor mode, return the old SR for UserState()."""
        cpu = ctx.cpu
        old_sr = cpu.r_sr()
        cpu.w_sr(old_sr | 0x2000)
        cpu.w_reg(REG_D0, old_sr)
        log_exec.info("SuperState: old SR=%04x", old_sr)

    def UserState(self, ctx, sysStack):
        """restore the SR saved by SuperState()."""
        cpu = ctx.cpu
        old_sr = cpu.r_sr()
        cpu.w_sr(sysStack & 0xFFFF)
        cpu.w_reg(REG_D0, old_sr)
        log_exec.info("UserState: sysStack=%08x -> old SR=%04x", sysStack, old_sr)

    # ----- interrupt vectors / servers -----

    def SetIntVector(self, ctx, intNumber, interrupt: InterruptStruct):
        vec = self.exec_lib.int_vects[intNumber]
        old = vec.iv_Node.aptr
        # only exception handler vectors keep the Interrupt node (AROS)
        is_handler = intNumber <= 2 or 6 <= intNumber <= 12
        vec.iv_Node.aptr = interrupt.addr if (is_handler and interrupt) else 0
        if interrupt:
            vec.iv_Data.aptr = interrupt.is_Data.aptr
            vec.iv_Code.aptr = interrupt.is_Code.aptr
        else:
            vec.iv_Data.aptr = 0xFFFFFFFF
            vec.iv_Code.aptr = 0xFFFFFFFF
        log_exec.info("SetIntVector(%d, %s) -> old=%08x", intNumber, interrupt, old)
        return old

    def AddIntServer(self, ctx, intNumber, interrupt: InterruptStruct):
        """chain an interrupt server on the vector's singly-linked list."""
        if interrupt is None:
            log_exec.warning("AddIntServer(%d): NULL interrupt", intNumber)
            return
        vec = self.exec_lib.int_vects[intNumber]
        node = interrupt.addr
        # insert at the head: is_Node.ln_Succ = old head
        ctx.mem.w32(node, vec.iv_Node.aptr)
        vec.iv_Node.aptr = node
        log_exec.info("AddIntServer(%d, %06x)", intNumber, node)

    def RemIntServer(self, ctx, intNumber, interrupt: InterruptStruct):
        if interrupt is None:
            log_exec.warning("RemIntServer(%d): NULL interrupt", intNumber)
            return
        vec = self.exec_lib.int_vects[intNumber]
        target = interrupt.addr
        head = vec.iv_Node.aptr
        if head == target:
            vec.iv_Node.aptr = ctx.mem.r32(target)
        else:
            pred = head
            while pred:
                succ = ctx.mem.r32(pred)
                if succ == target:
                    ctx.mem.w32(pred, ctx.mem.r32(target))
                    break
                pred = succ
        ctx.mem.w32(target, 0)
        log_exec.info("RemIntServer(%d, %06x)", intNumber, target)
