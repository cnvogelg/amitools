from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.lib.util.TagList import *
from amitools.vamos.lib.util.AmiDate import *
from amitools.vamos.log import *

from math import trunc


class UtilityLibrary(LibImpl):
    def UDivMod32(self, ctx):
        dividend = ctx.cpu.r_reg(REG_D0)
        divisor = ctx.cpu.r_reg(REG_D1)
        quot = dividend // divisor
        rem = dividend % divisor
        log_utility.info(
            "UDivMod32(dividend=%u, divisor=%u) => (quotient=%u, remainder=%u)"
            % (dividend, divisor, quot, rem)
        )
        return [quot, rem]

    def SDivMod32(self, ctx):
        dividend = ctx.cpu.r_reg(REG_D0)
        if dividend >= 0x80000000:
            dividend = dividend - 0x100000000
        divisor = ctx.cpu.r_reg(REG_D1)
        if divisor >= 0x80000000:
            divisor = divisor - 0x100000000

        # python modulos differs from c modulo
        quot = trunc(float(dividend) / divisor)
        rem = dividend - divisor * quot

        if quot < 0:
            quot = quot + 0x100000000
        if rem < 0:
            rem = rem + 0x100000000
        log_utility.info(
            "SDivMod32(dividend=%u, divisor=%u) => (quotient=%u, remainder=%u)"
            % (dividend, divisor, quot, rem)
        )
        return [quot, rem]

    def UMult32(self, ctx):
        a = ctx.cpu.r_reg(REG_D0)
        b = ctx.cpu.r_reg(REG_D1)
        c = (a * b) & 0xFFFFFFFF
        log_utility.info("UMult32(a=%u, b=%u) => %u", a, b, c)
        return c

    def SMult32(self, ctx):
        # Z_{2^32} is a ring. It does not matter whether we multiply signed or unsigned
        a = ctx.cpu.r_reg(REG_D0)
        b = ctx.cpu.r_reg(REG_D1)
        c = (a * b) & 0xFFFFFFFF
        log_utility.info("SMult32(a=%d, b=%d) => %d", a, b, c)
        return c

    def ToUpper(self, ctx):
        a = ctx.cpu.r_reg(REG_D0) & 0xFF
        return ord(chr(a).upper())

    def Stricmp(self, ctx):
        str1_addr = ctx.cpu.r_reg(REG_A0)
        str2_addr = ctx.cpu.r_reg(REG_A1)
        str1 = ctx.mem.r_cstr(str1_addr)
        str2 = ctx.mem.r_cstr(str2_addr)
        log_utility.info(
            'Stricmp(%08x="%s",%08x="%s")' % (str1_addr, str1, str2_addr, str2)
        )
        if str1.lower() < str2.lower():
            return -1
        elif str1.lower() > str2.lower():
            return +1
        else:
            return 0

    def Strnicmp(self, ctx):
        str1_addr = ctx.cpu.r_reg(REG_A0)
        str2_addr = ctx.cpu.r_reg(REG_A1)
        length = ctx.cpu.r_reg(REG_D0)
        str1 = ctx.mem.r_cstr(str1_addr)[:length]
        str2 = ctx.mem.r_cstr(str2_addr)[:length]
        log_utility.info(
            'Strnicmp(%08x="%s",%08x="%s")' % (str1_addr, str1, str2_addr, str2)
        )
        if str1.lower() < str2.lower():
            return -1
        elif str1.lower() > str2.lower():
            return +1
        else:
            return 0

    # Tags

    def NextTagItem(self, ctx):
        ti_ptr_addr = ctx.cpu.r_reg(REG_A0)
        ti_addr = ctx.mem.r32(tr_ptr_addr)
        ti_addr = next_tag_item(ctx, ti_addr)
        if ti_addr is None:
            next_addr = 0
        else:
            next_addr = ti_addr + 8
        ctx.mem.w32(tr_ptr_addr, next_addr)
        return ti_addr

    def FindTagItem(self, ctx):
        tagValue = ctx.cpu.r_reg(REG_D0)
        ti_addr = ctx.cpu.r_reg(REG_A0)
        if ti_addr == 0:
            return 0
        while True:
            ti_addr = next_tag_item(ctx, ti_addr)
            if ti_addr is None:
                return 0
            tag, _ = get_tag(ctx, ti_addr)
            if tag == tagValue:
                return ti_addr
            ti_addr += 8

    def GetTagData(self, ctx):
        defaultValue = ctx.cpu.r_reg(REG_D1)
        ti_addr = self.FindTagItem(ctx)
        if ti_addr != 0:
            return get_tag(ctx, ti_addr)[1]
        else:
            return defaultValue

    # ---- Date -----

    def Amiga2Date(self, ctx):
        seconds = ctx.cpu.r_reg(REG_D0)
        date_ptr = ctx.cpu.r_reg(REG_A0)

        t = date_at(seconds)
        log_utility.info("Amiga2Date: seconds=%d -> time=%s", seconds, t)
        write_clock_data(t, ctx.mem, date_ptr)

    def Date2Amiga(self, ctx):
        date_ptr = ctx.cpu.r_reg(REG_A0)

        t = read_clock_data(ctx.mem, date_ptr)
        if t is None:
            log_utility.warning("Date2Amiga: invalid date! @%08x", date_ptr)
            return 0
        seconds = seconds_since(t)
        log_utility.info("Date2Amige: time=%s -> seconds=%u", t, seconds)
        return seconds

    def CheckDate(self, ctx):
        date_ptr = ctx.cpu.r_reg(REG_A0)

        t = read_clock_data(ctx.mem, date_ptr)
        if t is None:
            log_utility.info("CheckDate: invalid date! @%08x", date_ptr)
            return 0
        seconds = seconds_since(t)
        log_utility.info("CheckDate: time=%s -> seconds=%u", t, seconds)
        return seconds
