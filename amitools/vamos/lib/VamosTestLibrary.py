from __future__ import print_function

from amitools.vamos.CPU import *
from amitools.vamos.libcore import LibImpl

class VamosTestLibrary(LibImpl):

  def InvalidFunc(self, ctx):
    """a test function that does not exist in the .fd file"""
    pass

  def PrintHello(self, ctx):
    print("VamosTest: PrintHello()")

  def PrintString(self, ctx):
    str_addr = ctx.cpu.r_reg(REG_A0)
    txt = ctx.mem.r_cstr(str_addr)
    print("VamosTest: PrintString(%s)", txt)

  def Add(self, ctx):
    a = ctx.cpu.r_reg(REG_D0)
    b = ctx.cpu.r_reg(REG_D1)
    return a + b

  def Swap(self, ctx):
    a = ctx.cpu.r_reg(REG_D0)
    b = ctx.cpu.r_reg(REG_D1)
    return b, a

  def RaiseError(self, ctx):
    raise RuntimeError("VamosTest: RaiseError()")
