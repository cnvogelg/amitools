import sys

from amitools.vamos.log import log_exec
from amitools.vamos.machine.regs import REG_A0, REG_A1, REG_A2, REG_A3

from .RawDoFmt import raw_do_fmt


class RawIOMixin:
    """exec.library raw IO LVOs (fd banner: private diagnostic support)."""

    def RawDoFmt(self, ctx):
        fmtString = ctx.cpu.r_reg(REG_A0)
        dataStream = ctx.cpu.r_reg(REG_A1)
        putProc = ctx.cpu.r_reg(REG_A2)
        putData = ctx.cpu.r_reg(REG_A3)
        dataStream, fmt, resultstr, known = raw_do_fmt(
            ctx, fmtString, dataStream, putProc, putData
        )
        log_exec.info(
            "RawDoFmt: fmtString=%s -> %s (known=%s, dataStream=%06x)"
            % (fmt, resultstr, known, dataStream)
        )
        return dataStream

    def RawPutChar(self, ctx, ch):
        value = ch & 0xFF
        self._raw_console_write(value)
        log_exec.info("RawPutChar(%02x)", value)

    def RawMayGetChar(self, ctx):
        log_exec.info("RawMayGetChar() -> no data")
        return -1

    def _raw_console_write(self, value):
        if value == 0:
            return
        out = sys.stderr
        if value == 10:
            out.write("\r")
        out.write(chr(value & 0xFF))
        out.flush()
