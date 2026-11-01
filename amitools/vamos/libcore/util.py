from amitools.vamos.machine.regs import REG_D0


SR_CARRY = 0x0001
SR_OVERFLOW = 0x0002
SR_ZERO = 0x0004
SR_NEGATIVE = 0x0008
SR_EXTEND = 0x0010
SR_PRESERVE_MASK = 0xFF00 | SR_EXTEND
SR_CONDITION_CODE_MASK = SR_CARRY | SR_OVERFLOW | SR_ZERO | SR_NEGATIVE


def set_sr_from_d0(ctx):
    sr = ctx.cpu.r_sr() & SR_PRESERVE_MASK
    sr &= ~SR_CONDITION_CODE_MASK
    val = ctx.cpu.r_reg(REG_D0) & 0xFFFFFFFF
    if val == 0:
        sr |= SR_ZERO
    if val & 0x80000000:
        sr |= SR_NEGATIVE
    ctx.cpu.w_sr(sr)
