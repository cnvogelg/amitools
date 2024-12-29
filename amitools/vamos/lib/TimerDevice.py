import time
from amitools.vamos.libcore import LibImpl
from amitools.vamos.machine.regs import REG_A0
from amitools.vamos.libstructs import TimeValStruct


class TimerDevice(LibImpl):
    # our simulated EClock freq: 10 MHz
    # its around the real EClock (3 MHz)
    ECLOCK_HZ = 10_000_000
    # how to convert ns time stamp to eclock
    ECLOCK_NS_FACTOR = 100

    def _get_eclock_lo_hi(self):
        # use the monotonic time here to have a suitable clock for benchmarks
        ts_ns = time.monotonic_ns()
        eclk = ts_ns // self.ECLOCK_NS_FACTOR
        eclk_lo = eclk & 0xFFFFFFFF
        eclk_hi = eclk >> 32
        return eclk_lo, eclk_hi

    def ReadEClock(self, ctx):
        addr = ctx.cpu.r_reg(REG_A0)
        # get val struct
        tv = TimeValStruct(mem=ctx.mem, addr=addr)

        lo, hi = self._get_eclock_lo_hi()
        tv.secs.val = hi
        tv.micro.val = lo

        # always return eclock freq
        return self.ECLOCK_HZ
