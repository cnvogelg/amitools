from amitools.vamos.AmigaLibrary import *
from amitools.vamos.lib.lexec.ExecStruct import LibraryDef
from amitools.vamos.lib.util.UtilStruct import TagItemDef
from amitools.vamos.lib.util.TagList import *
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
    a = ctx.cpu.r_reg(REG_D0)
    return ord(chr(a).upper())

  def Stricmp(self, ctx):
    str1_addr = ctx.cpu.r_reg(REG_A0)
    str2_addr = ctx.cpu.r_reg(REG_A1)
    str1 = ctx.mem.access.r_cstr(str1_addr)
    str2 = ctx.mem.access.r_cstr(str2_addr)
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
    if str1.lower() < str2.lower():
      return -1
    elif str1.lower() > str2.lower():
      return +1
    else:
      return 0

  # Tags

  def NextTagItem(self, ctx):
    ti_ptr_addr = ctx.cpu.r_reg(REG_A0)
    ti_addr = ctx.mem.access.r32(tr_ptr_addr)
    ti_addr = next_tag_item(ctx, ti_addr)
    if ti_addr is None:
      next_addr = 0
    else:
      next_addr = ti_addr + 8
    ctx.mem.access.w32(tr_ptr_addr, next_addr)
    return ti_addr

  def FindTagItem(self, ctx):
    tagValue = ctx.cpu.r_reg(REG_D0)
    ti_addr = ctx.cpu.r_reg(REG_A0)
    if ti_addr == 0:
      return 0
    while True:
      ti_addr = next_tag_item(ctx, ti_addr)
      if ti_addr is None:
        return 0
      tag, _ = get_tag(ctx, ti_addr)
      if tag == tagValue:
        return ti_addr
      ti_addr += 8

  def GetTagData(self, ctx):
    defaultValue = ctx.cpu.r_reg(REG_D1)
    ti_addr = self.FindTagItem(ctx)
    if ti_addr != 0:
      return get_tag(ctx, ti_addr)[1]
    else:
      return defaultValue
