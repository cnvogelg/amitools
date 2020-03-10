from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.log import log_math
from amitools.util.Math import *
import math


class MathIEEEDoubTransLibrary(LibImpl):
    def IEEEDPAcos(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        try:
            res = math.acos(arg)
        except ValueError:
            res = float("-nan")
        log_math.info("DPAcos(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPAsin(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        try:
            res = math.asin(arg)
        except ValueError:
            if arg < 0.0:
                res = float("nan")
            else:
                res = float("-nan")
        log_math.info("DPAsin(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPAtan(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        res = math.atan(arg)
        log_math.info("DPAtan(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPCos(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        res = math.cos(arg)
        log_math.info("DPCos(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPCosh(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        try:
            res = math.cosh(arg)
        except OverflowError:
            res = float("inf")
        log_math.info("DPCosh(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPExp(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        try:
            res = math.exp(arg)
        except OverflowError:
            res = float("inf")
        log_math.info("DPExp(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPFieee(self, ctx):
        arg = reg_to_float(ctx.cpu.r_reg(REG_D0))
        log_math.info("DPFieee(%s)", arg)
        return double_to_regs(arg)

    def IEEEDPLog(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        try:
            if arg == 0.0:
                res = float("-inf")
            else:
                res = math.log(arg)
        except ValueError:
            res = float("-nan")
        log_math.info("DPLog(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPLog10(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        try:
            if arg == 0.0:
                res = float("-inf")
            else:
                res = math.log10(arg)
        except ValueError:
            res = float("-nan")
        log_math.info("DPLog10(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPPow(self, ctx):
        a = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        b = regs_to_double(ctx.cpu.r_reg(REG_D2), ctx.cpu.r_reg(REG_D3))
        try:
            res = math.pow(a, b)
        except OverflowError:
            res = float("inf")
        log_math.info("DPPow(%s, %s) = %s", a, b, res)
        return double_to_regs(res)

    def IEEEDPSin(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        res = math.sin(arg)
        log_math.info("DPSin(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPSincos(self, ctx):
        ptr = ctx.cpu.r_reg(REG_A0)
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        res_sin = math.sin(arg)
        res_cos = math.cos(arg)
        log_math.info("DPSincos(%s) = %s, %s", arg, res_sin, res_cos)
        vals_sin = double_to_regs(res_sin)
        vals_cos = double_to_regs(res_cos)
        # write cos to ptr
        ctx.mem.w32(ptr, vals_cos[0])
        ctx.mem.w32(ptr + 4, vals_cos[1])
        return vals_sin

    def IEEEDPSinh(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        try:
            res = math.sinh(arg)
        except OverflowError:
            if arg < 0:
                res = float("-inf")
            else:
                res = float("inf")
        log_math.info("DPSinh(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPSqrt(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        try:
            res = math.sqrt(arg)
        except ValueError:
            res = float("-nan")
        log_math.info("DPSqrt(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPTan(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        res = math.tan(arg)
        log_math.info("DPTan(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPTanh(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        res = math.tanh(arg)
        log_math.info("DPTanh(%s) = %s", arg, res)
        return double_to_regs(res)

    def IEEEDPTieee(self, ctx):
        arg = regs_to_double(ctx.cpu.r_reg(REG_D0), ctx.cpu.r_reg(REG_D1))
        log_math.info("DPTieee(%s)", arg)
        return float_to_reg(arg)
