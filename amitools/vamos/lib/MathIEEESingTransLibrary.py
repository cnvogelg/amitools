from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.log import log_math
from amitools.util.Math import *
import math


class MathIEEESingTransLibrary(LibImpl):
    def IEEESPAcos(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            res = math.acos(arg)
        except ValueError:
            res = float("-nan")
        log_math.info("SPAcos(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPAsin(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            res = math.asin(arg)
        except ValueError:
            if arg < 0.0:
                res = float("nan")
            else:
                res = float("-nan")
        log_math.info("SPAsin(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPAtan(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        res = math.atan(arg)
        log_math.info("SPAtan(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPCos(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        res = math.cos(arg)
        log_math.info("SPCos(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPCosh(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            res = math.cosh(arg)
        except OverflowError:
            res = float("inf")
        log_math.info("SPCosh(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPExp(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            res = math.exp(arg)
        except OverflowError:
            res = float("inf")
        log_math.info("SPExp(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPFieee(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        log_math.info("SPFieee(%s)", arg)
        return float_to_reg(arg)

    def IEEESPLog(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            if arg == 0.0:
                res = float("-inf")
            else:
                res = math.log(arg)
        except ValueError:
            res = float("-nan")
        log_math.info("SPLog(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPLog10(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            if arg == 0.0:
                res = float("-inf")
            else:
                res = math.log10(arg)
        except ValueError:
            res = float("-nan")
        log_math.info("SPLog10(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPPow(self, ctx):
        a = reg_to_float(ctx.cpu.r_reg(REG_D0))
        b = reg_to_float(ctx.cpu.r_reg(REG_D1))
        try:
            res = math.pow(a, b)
        except OverflowError:
            res = float("inf")
        log_math.info("SPPow(%s, %s) = %s", a, b, res)
        return float_to_reg(res)

    def IEEESPSin(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        res = math.sin(arg)
        log_math.info("SPSin(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPSincos(self, ctx):
        ptr = ctx.cpu.r_reg(REG_A0)
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        res_sin = math.sin(arg)
        res_cos = math.cos(arg)
        log_math.info("SPSincos(%s) = %s, %s", arg, res_sin, res_cos)
        vals_sin = float_to_reg(res_sin)
        vals_cos = float_to_reg(res_cos)
        # write cos to ptr
        ctx.mem.w32(ptr, vals_cos)
        return vals_sin

    def IEEESPSinh(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            res = math.sinh(arg)
        except OverflowError:
            if arg < 0:
                res = float("-inf")
            else:
                res = float("inf")
        log_math.info("SPSinh(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPSqrt(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        try:
            res = math.sqrt(arg)
        except ValueError:
            res = float("-nan")
        log_math.info("SPSqrt(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPTan(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        res = math.tan(arg)
        log_math.info("SPTan(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPTanh(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        res = math.tanh(arg)
        log_math.info("SPTanh(%s) = %s", arg, res)
        return float_to_reg(res)

    def IEEESPTieee(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        log_math.info("SPTieee(%s)", arg)
        return float_to_reg(arg)
