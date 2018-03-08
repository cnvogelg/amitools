from amitools.vamos.AmigaLibrary import *
from amitools.vamos.lib.lexec.ExecStruct import LibraryDef
from amitools.vamos.Log import log_math
from amitools.util.Math import *


class MathTransLibrary(AmigaLibrary):
  name = "mathtrans.library"

  def __init__(self, config):
    AmigaLibrary.__init__(self, self.name, LibraryDef, config)

  def setup_lib(self, ctx):
    AmigaLibrary.setup_lib(self, ctx)

  def SPAtan(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPSin(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPCos(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPTan(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPSincos(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)
    cos_ptr = ctx.cpu.r_reg(REG_D1)

  def SPSinh(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPCosh(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPTanh(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPExp(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPLog(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPPow(self, ctx):
    power = ctx.cpu.r_reg(REG_D1)
    arg = ctx.cpu.r_reg(REG_D0)

  def SPSqrt(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPTieee(self, ctx):
    """convert to IEEE float"""
    val = ctx.cpu.r_reg(REG_D0)
    flt = ffp_reg_to_float(val)
    log_math.info("SPTieee(%08x) = %s", val, flt)
    return float_to_reg(flt)

  def SPFieee(self, ctx):
    """convert from IEEE float"""
    val = ctx.cpu.r_reg(REG_D0)
    flt = reg_to_float(val)
    ffp = float_to_ffp_reg(flt)
    log_math.info("SPFieee(%s) = %08x", flt, ffp)
    return ffp

  def SPAsin(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPAcos(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPLog10(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)
