from amitools.vamos.libcore import LibImpl
from amitools.vamos.machine.regs import REG_A0
from amitools.vamos.astructs import AccessStruct
from amitools.vamos.libstructs.dos import TimeValStruct

from datetime import datetime


class TimerDevice(LibImpl):
    def ReadEClock(self, ctx):
        eclockval = ctx.cpu.r_reg(REG_A0)

        dt = datetime.now()

        tv = AccessStruct(ctx.mem, TimeValStruct, struct_addr=eclockval)
        tv.tv_secs = dt.microsecond / 1000000
        tv.tv_micros = dt.microsecond % 1000000

        return 50

    def GetSysTime(self, ctx):
        self.ReadEClock(ctx)
