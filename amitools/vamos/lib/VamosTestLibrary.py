

from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.error import *

class VamosTestLibrary(LibImpl):

  def setup_lib(self, ctx, base_addr):
    self.cnt = 0

  def finish_lib(self, ctx):
    self.cnt = None

  def open_lib(self, ctx, open_cnt):
    self.cnt = open_cnt

  def close_lib(self, ctx, open_cnt):
    self.cnt = open_cnt

  def get_version(self):
    return 23

  def get_cnt(self):
    return self.cnt

  def ignore_func(self):
    """a lower-case function that is ignored"""
    pass

  def InvalidFunc(self, ctx):
    """a test function that does not exist in the .fd file"""
    pass

  def PrintHello(self, ctx):
    print("VamosTest: PrintHello()")
    return 0

  def PrintString(self, ctx):
    str_addr = ctx.cpu.r_reg(REG_A0)
    txt = ctx.mem.r_cstr(str_addr)
    print("VamosTest: PrintString(%s)", txt)
    return 0

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
