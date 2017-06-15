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

class MathIEEEDoubBasLibrary(AmigaLibrary):
  name = "mathieeedoubbas.library"

  def __init__(self, config):
    AmigaLibrary.__init__(self, self.name, LibraryDef, config)

  def setup_lib(self, ctx):
    AmigaLibrary.setup_lib(self, ctx)

  def IEEEDPFix(self, ctx):
    arg=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    return int(arg)

  def IEEEFlt(self, ctx):
    (hi,lo)=fromDouble(ctx.cpu.r_reg(REG_D0)+0.0)
    ctx.cpu.w_reg(REG_D1,lo)
    return hi

  def IEEEDPCmp(self, ctx):
    arg1=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    arg2=toDouble(ctx.cpu.r_reg(REG_D2),ctx.cpu.r_reg(REG_D3))
    if arg1<arg2:
      return -1
    elif arg1>arg2:
      return +1
    else:
      return 0
    
  def IEEEDPTst(self,ctx):
    arg1=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    if arg1<0.0:
      return -1
    elif arg1>0.0:
      return +1
    else:
      return 0

  def IEEEDPAbs(self,ctx):
    arg1=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    if arg1<0:
      arg1=-arg1
    (hi,lo)=fromDouble(arg1)
    ctx.cpu.w_reg(REG_D1,lo)
    return hi

  def IEEEDPAdd(self,ctx):
    arg1=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    arg2=toDouble(ctx.cpu.r_reg(REG_D2),ctx.cpu.r_reg(REG_D3))
    print "%s + %s = %s" % (arg1,arg,arg1+arg2)
    (hi,lo)=fromDouble(arg1+arg2)
    ctx.cpu.w_reg(REG_D1,lo)
    return hi

  def IEEEDPSub(self,ctx):
    arg1=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    arg2=toDouble(ctx.cpu.r_reg(REG_D2),ctx.cpu.r_reg(REG_D3))
    print "%s - %s = %s" % (arg1,arg,arg1-arg2)
    (hi,lo)=fromDouble(arg1-arg2)
    ctx.cpu.w_reg(REG_D1,lo)
    return hi
  
  def IEEEDPMul(self,ctx):
    arg1=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    arg2=toDouble(ctx.cpu.r_reg(REG_D2),ctx.cpu.r_reg(REG_D3))
    print "%s * %s = %s" % (arg1,arg,arg1*arg2)
    (hi,lo)=fromDouble(arg1*arg2)
    ctx.cpu.w_reg(REG_D1,lo)
    return hi
  
  def IEEEDPDiv(self,ctx):
    arg1=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    arg2=toDouble(ctx.cpu.r_reg(REG_D2),ctx.cpu.r_reg(REG_D3))
    print "%s / %s = %s" % (arg1,arg,arg1/arg2)
    (hi,lo)=fromDouble(arg1/arg2)
    ctx.cpu.w_reg(REG_D1,lo)
    return hi
  
  def IEEEDPFloor(self,ctx):
    arg1=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    (hi,lo)=fromDouble(math.floor(arg1))
    ctx.cpu.w_reg(REG_D1,lo)
    return hi
  
  def IEEEDPCeil(self,ctx):
    arg1=toDouble(ctx.cpu.r_reg(REG_D0),ctx.cpu.r_reg(REG_D1))
    (hi,lo)=fromDouble(math.ceil(arg1))
    ctx.cpu.w_reg(REG_D1,lo)
    return hi

