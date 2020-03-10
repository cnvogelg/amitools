from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.log import log_math
from amitools.util.Math import *


class MathTransLibrary(LibImpl):
    def SPAcos(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            res = math.acos(arg)
        except ValueError:
            res = float("-nan")
        log_math.info("SPAcos(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPAsin(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            res = math.asin(arg)
        except ValueError:
            if arg < 0.0:
                res = float("nan")
            else:
                res = float("-nan")
        log_math.info("SPAsin(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPAtan(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        res = math.atan(arg)
        log_math.info("SPAtan(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPCos(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        res = math.cos(arg)
        log_math.info("SPCos(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPCosh(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            res = math.cosh(arg)
        except OverflowError:
            res = float("inf")
        log_math.info("SPCosh(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPExp(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            res = math.exp(arg)
        except OverflowError:
            res = float("inf")
        log_math.info("SPExp(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPFieee(self, ctx):
        val = ctx.cpu.r_reg(REG_D0)
        flt = reg_to_float(val)
        ffp = float_to_ffp_reg(flt)
        log_math.info("SPFieee(%s) = %08x", flt, ffp)
        return ffp

    def SPLog(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            if arg == 0.0:
                res = float("-inf")
            else:
                res = math.log(arg)
        except ValueError:
            res = float("-nan")
        log_math.info("SPLog(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPLog10(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            if arg == 0.0:
                res = float("-inf")
            else:
                res = math.log10(arg)
        except ValueError:
            res = float("-nan")
        log_math.info("SPLog10(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPPow(self, ctx):
        a = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        b = ffp_reg_to_float(ctx.cpu.r_reg(REG_D1))
        try:
            res = math.pow(a, b)
        except OverflowError:
            res = float("inf")
        log_math.info("SPPow(%s, %s) = %s", a, b, res)
        return float_to_ffp_reg(res)

    def SPSin(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        res = math.sin(arg)
        log_math.info("SPSin(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPSincos(self, ctx):
        ptr = ctx.cpu.r_reg(REG_D1)
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        res_sin = math.sin(arg)
        res_cos = math.cos(arg)
        log_math.info("SPSincos(%s) = %s, %s", arg, res_sin, res_cos)
        vals_sin = float_to_ffp_reg(res_sin)
        vals_cos = float_to_ffp_reg(res_cos)
        # write cos to ptr
        ctx.mem.w32(ptr, vals_cos)
        return vals_sin

    def SPSinh(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            res = math.sinh(arg)
        except OverflowError:
            if arg < 0:
                res = float("-inf")
            else:
                res = float("inf")
        log_math.info("SPSinh(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPSqrt(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            res = math.sqrt(arg)
        except ValueError:
            res = float("-nan")
        log_math.info("SPSqrt(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPTan(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        res = math.tan(arg)
        log_math.info("SPTan(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPTanh(self, ctx):
        arg = ffp_reg_to_float(ctx.cpu.r_reg(REG_D0))
        res = math.tanh(arg)
        log_math.info("SPTanh(%s) = %s", arg, res)
        return float_to_ffp_reg(res)

    def SPTieee(self, ctx):
        val = ctx.cpu.r_reg(REG_D0)
        flt = ffp_reg_to_float(val)
        log_math.info("SPTieee(%08x) = %s", val, flt)
        return float_to_reg(flt)
