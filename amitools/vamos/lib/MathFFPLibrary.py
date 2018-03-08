from amitools.vamos.AmigaLibrary import *
from amitools.vamos.lib.lexec.ExecStruct import LibraryDef
from amitools.vamos.Log import log_math

class MathFFPLibrary(AmigaLibrary):
  name = "mathffp.library"

  def __init__(self, config):
    AmigaLibrary.__init__(self, self.name, LibraryDef, config)

  def setup_lib(self, ctx):
    AmigaLibrary.setup_lib(self, ctx)

  def SPFix(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPFlt(self, ctx):
    int_val = ctx.cpu.r_reg(REG_D0)

  def SPCmp(self, ctx):
    a = ctx.cpu.r_reg(REG_D1)
    b = ctx.cpu.r_reg(REG_D0)

  def SPTst(self, ctx):
    val = ctx.cpu.r_reg(REG_D1)

  def SPAbs(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPNeg(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPAdd(self, ctx):
    a = ctx.cpu.r_reg(REG_D1)
    b = ctx.cpu.r_reg(REG_D0)

  def SPSub(self, ctx):
    a = ctx.cpu.r_reg(REG_D1)
    b = ctx.cpu.r_reg(REG_D0)

  def SPMul(self, ctx):
    a = ctx.cpu.r_reg(REG_D1)
    b = ctx.cpu.r_reg(REG_D0)

  def SPDiv(self, ctx):
    a = ctx.cpu.r_reg(REG_D1)
    b = ctx.cpu.r_reg(REG_D0)

  def SPFloor(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)

  def SPCeil(self, ctx):
    val = ctx.cpu.r_reg(REG_D0)
