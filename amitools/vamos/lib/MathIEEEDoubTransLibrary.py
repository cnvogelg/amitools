from amitools.vamos.AmigaLibrary import *
from amitools.vamos.lib.lexec.ExecStruct import LibraryDef
from amitools.vamos.Log import *
import struct
import math

def fromDouble(number):
  hi=0
  lo=0
  st=struct.pack('>d',number)
  for c in st[0:4]:
    hi=(hi << 8) | ord(c)
  for c in st[4:8]:
    lo=(lo << 8) | ord(c)
  return (hi,lo)

def toDouble(hi,lo):
  st=""
  for i in range(0,4):
    st=st+chr(hi >> 24)
    hi=(hi << 8) & 0xffffffff
  for i in range(0,4):
    st=st+chr(lo >> 24)
    lo=(lo << 8) & 0xffffffff
  return struct.unpack('>d',st)[0]

class MathIEEEDoubTransLibrary(AmigaLibrary):
  name = "mathieeedoubtrans.library"

  def __init__(self, config):
    AmigaLibrary.__init__(self, self.name, LibraryDef, config)

  def setup_lib(self, ctx):
    AmigaLibrary.setup_lib(self, ctx)

#selco    
  def IEEEDPSqrt(self,ctx):
    arg=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    if arg < 0: # we should not crash for negative numbers!
#      (hi,lo)=fromDouble(float('nan')  # not a number (7ff80000 00000000)
      (hi,lo)=(0xfff80000,0)            # not a number, this is what is returned under AmigaOS3.9
    else:
      (hi,lo)=fromDouble(math.sqrt(arg))
    ctx.cpu.w_reg(REG_D1,lo)
    return hi

#selco    
  def IEEEDPCosh(self,ctx):
    arg=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    (hi,lo)=fromDouble(math.cosh(arg))
    ctx.cpu.w_reg(REG_D1,lo)
    return hi

#selco    
  def IEEEDPAcos(self,ctx):
    arg=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    (hi,lo)=fromDouble(math.acos(arg))
    ctx.cpu.w_reg(REG_D1,lo)
    return hi

#selco    
  def IEEEDPLog10(self,ctx):
    arg=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    if arg <= 0: # we should not crash for negative numbers!
#      (hi,lo)=fromDouble(float('nan')  # not a number (7ff80000 00000000)
      (hi,lo)=(0xfff80000,0)            # not a number, this is what is returned under AmigaOS3.9
    else:
      (hi,lo)=fromDouble(math.log10(arg))
    ctx.cpu.w_reg(REG_D1,lo)
    return hi

