from __future__ import print_function

from amitools.vamos.CPU import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.Exceptions import *

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
    str_addr = ctx.cpu.r_reg(REG_A0)
    txt = ctx.mem.r_cstr(str_addr)
    if txt == "RuntimeError":
      e = RuntimeError("VamosTest")
    elif txt == "VamosInternalError":
      e = VamosInternalError("VamosTest")
    elif txt == "InvalidMemoryAccessError":
      e = InvalidMemoryAccessError('R', 2, 0x200)
    else:
      print("VamosTest: Invalid Error:", txt)
      return
    print("VamosTest: raise", e.__class__.__name__)
    raise e
