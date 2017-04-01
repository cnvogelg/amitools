from amitools.vamos.AmigaLibrary import *
from amitools.vamos.lib.lexec.ExecStruct import LibraryDef
from amitools.vamos.Log import *

class UtilityLibrary(AmigaLibrary):
  name = "utility.library"

  def __init__(self, config):
    AmigaLibrary.__init__(self, self.name, LibraryDef, config)

  def setup_lib(self, ctx):
    AmigaLibrary.setup_lib(self, ctx)

  def UDivMod32(self, ctx):
    dividend = ctx.cpu.r_reg(REG_D0)
    divisor = ctx.cpu.r_reg(REG_D1)
    quot = dividend / divisor
    rem  = dividend % divisor
    log_utility.info("UDivMod32(dividend=%u, divisor=%u) => (quotient=%u, remainder=%u)" % (dividend, divisor, quot, rem))
    return [quot, rem]

  def UMult32(self, ctx):
    a = ctx.cpu.r_reg(REG_D0)
    b = ctx.cpu.r_reg(REG_D1)
    c = (a * b) & 0xffffffff
    log_utility.info("UMult32(a=%u, b=%u) => %u", a, b, c)
    return c

  def SMult32(self, ctx):
    # Z_{2^32} is a ring. It does not matter whether we multiply signed or unsigned
    a = ctx.cpu.r_reg(REG_D0)
    b = ctx.cpu.r_reg(REG_D1)
    c = (a * b) & 0xffffffff
    log_utility.info("SMult32(a=%d, b=%d) => %d", a, b, c)
    return c

  def ToUpper(self, ctx):
    a = ctx.cpu.r_reg(REG_D0) & 0xff
    return ord(chr(a).upper())

  def Stricmp(self, ctx):
    str1_addr = ctx.cpu.r_reg(REG_A0)
    str2_addr = ctx.cpu.r_reg(REG_A1)
    str1 = ctx.mem.access.r_cstr(str1_addr)
    str2 = ctx.mem.access.r_cstr(str2_addr)
    log_utility.info("Stricmp(%08x=\"%s\",%08x=\"%s\")" % (str1_addr,str1,str2_addr,str2))
    if str1.lower() < str2.lower():
      return -1
    elif str1.lower() > str2.lower():
      return +1
    else:
      return 0

  def Strnicmp(self, ctx):
    str1_addr = ctx.cpu.r_reg(REG_A0)
    str2_addr = ctx.cpu.r_reg(REG_A1)
    length    = ctx.cpu.r_reg(REG_D0)
    str1 = ctx.mem.access.r_cstr(str1_addr)[:length]
    str2 = ctx.mem.access.r_cstr(str2_addr)[:length]
    log_utility.info("Strnicmp(%08x=\"%s\",%08x=\"%s\")" % (str1_addr,str1,str2_addr,str2))
    if str1.lower() < str2.lower():
      return -1
    elif str1.lower() > str2.lower():
      return +1
    else:
      return 0


