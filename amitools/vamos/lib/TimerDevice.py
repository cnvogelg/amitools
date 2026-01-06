import time
from amitools.vamos.libcore import LibImpl
from amitools.vamos.machine.regs import REG_A0
from amitools.vamos.astructs import LONG
from amitools.vamos.libtypes import TimeVal
from amitools.vamos.log import log_timer


class TimerDevice(LibImpl):
    # our simulated EClock freq: 10 MHz
    # its around the real EClock (3 MHz)
    ECLOCK_HZ = 10_000_000
    # how to convert ns time stamp to eclock
    ECLOCK_NS_FACTOR = 100
    # micros per second
    MICRO_HZ = 1_000_000

    @classmethod
    def get_sys_time(cls):
        """a static method so we could share it if needed

        return secs, micros
        """
        t = time.time()
        secs = int(t)
        micros = t - secs
        micros *= cls.MICRO_HZ
        micros = int(micros)
        return secs, micros

    @classmethod
    def get_eclock_lo_hi(cls):
        # use the monotonic time here to have a suitable clock for benchmarks
        ts_ns = time.monotonic_ns()
        eclk = ts_ns // cls.ECLOCK_NS_FACTOR
        eclk_lo = eclk & 0xFFFFFFFF
        eclk_hi = eclk >> 32
        return eclk_lo, eclk_hi

    def ReadEClock(self, ctx, tv: TimeVal):
        lo, hi = self.get_eclock_lo_hi()
        log_timer.info("ReadEClock(%s) -> lo=%d hi=%d", tv, lo, hi)
        tv.set_time_val(hi, lo)

        # always return eclock freq
        return self.ECLOCK_HZ

    def GetSysTime(self, ctx, tv: TimeVal):
        secs, micros = self.get_sys_time()
        log_timer.info("GetSysTime(%s) -> secs=%d micros=%d", tv, secs, micros)
        tv.set_time_val(secs, micros)

    def AddTime(self, ctx, dest: TimeVal, src: TimeVal):
        d_secs, d_micros = dest.get_time_val()
        s_secs, s_micros = src.get_time_val()
        # add seconds
        sum_secs = d_secs + s_secs
        # add micros
        sum_micros = d_micros + s_micros
        if sum_micros >= self.MICRO_HZ:
            sum_micros = sum_micros % self.MICRO_HZ
            sum_secs += 1
        log_timer.info(
            "AddTime(dest=%s:(%d, %d), src=%s:(%d, %d) -> secs=%d micro=%d",
            dest,
            d_secs,
            d_micros,
            src,
            s_secs,
            s_micros,
            sum_secs,
            sum_micros,
        )
        # write back result
        dest.set_time_val(sum_secs, sum_micros)

    def SubTime(self, ctx, dest: TimeVal, src: TimeVal):
        d_secs, d_micros = dest.get_time_val()
        s_secs, s_micros = src.get_time_val()
        # add seconds
        diff_secs = d_secs - s_secs
        # add micros
        if d_micros > s_micros:
            diff_micros = d_micros - s_micros
        else:
            diff_micros = d_micros + self.MICRO_HZ - s_micros
            diff_secs -= 1

        # limit values
        if diff_secs < 0:
            diff_secs = 0
        if diff_micros < 0:
            diff_micros = 0

        log_timer.info(
            "SubTime(dest=%s: (%d, %d), src=%s:(%d, %d) -> secs=%d micro=%d",
            dest,
            d_secs,
            d_micros,
            src,
            s_secs,
            s_micros,
            diff_secs,
            diff_micros,
        )
        # write back result
        dest.set_time_val(diff_secs, diff_micros)

    def CmpTime(self, ctx, dest: TimeVal, src: TimeVal):
        # 1: dest<src -1: dest>src 0:(dest==src)
        d_secs, d_micros = dest.get_time_val()
        s_secs, s_micros = src.get_time_val()
        if d_secs < s_secs:
            result = 1
        elif d_secs > s_secs:
            result = -1
        else:
            if d_micros < s_micros:
                result = 1
            elif d_micros > s_micros:
                result = -1
            else:
                result = 0
        log_timer.info("CmpTime(dest=%s, src=%s) -> %d", dest, src, result)
        return result
