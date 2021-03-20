from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.lib.util.TagList import *
from amitools.vamos.lib.util.AmiDate import *
from amitools.vamos.log import *

import string


class LocaleLibrary(LibImpl):
    def OpenLocale(self, ctx):
        name = ctx.cpu.r_reg(REG_A0)
        # dummy
        return 0

    def CloseLocale(self, ctx):
        locale = ctx.cpu.r_reg(REG_A0)
        # dummy - accept all

    def IsUpper(self, ctx):
        locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.uppercase

    def IsLower(self, ctx):
        locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.lowercase

    def IsDigit(self, ctx):
        locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.digits

    def IsPrint(self, ctx):
        locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.printable

    def IsCntrl(self, ctx):
        locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        # maybe not ok...
        return character < 32 and not chr(character) in string.printable

    def IsXDigit(self, ctx):
        locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.hexdigits

    def IsSpace(self, ctx):
        locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.whitespace

    def IsPunct(self, ctx):
        locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.punctuation

    def IsGraph(self, ctx):
        locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return (
            chr(character) in string.printable
            and not chr(character) in string.whitespace
        )


"""
  def CloseCatalog(self, ctx):
    catalog = ctx.cpu.r_reg(REG_A0)
    print "not implemented: CloseCatalog"

  def ConvToLower(self, ctx):
    locale = ctx.cpu.r_reg(REG_A0)
    character = ctx.cpu.r_reg(REG_D0)
    print "not implemented: ConvToLower"

  def ConvToUpper(self, ctx):
    locale = ctx.cpu.r_reg(REG_A0)
    character = ctx.cpu.r_reg(REG_D0)
    print "not implemented: ConvToUpper"

  def FormatDate(self, ctx):
    locale = ctx.cpu.r_reg(REG_A0)
    fmtTemplate = ctx.cpu.r_reg(REG_A1)
    date = ctx.cpu.r_reg(REG_A2)
    putCharFunc = ctx.cpu.r_reg(REG_A3)
    print "not implemented: FormatDate"

  def FormatString(self, ctx):
    locale = ctx.cpu.r_reg(REG_A0)
    fmtTemplate = ctx.cpu.r_reg(REG_A1)
    dataStream = ctx.cpu.r_reg(REG_A2)
    putCharFunc = ctx.cpu.r_reg(REG_A3)
    print "not implemented: FormatString"

  def GetCatalogStr(self, ctx):
    catalog = ctx.cpu.r_reg(REG_A0)
    defaultString = ctx.cpu.r_reg(REG_A1)
    stringNum = ctx.cpu.r_reg(REG_D0)
    print "not implemented: GetCatalogStr"

  def GetLocaleStr(self, ctx):
    locale = ctx.cpu.r_reg(REG_A0)
    stringNum = ctx.cpu.r_reg(REG_D0)
    print "not implemented: GetLocaleStr"

  def OpenCatalogA(self, ctx):
    locale = ctx.cpu.r_reg(REG_A0)
    name = ctx.cpu.r_reg(REG_A1)
    tagList = ctx.cpu.r_reg(REG_A2)
    print "not implemented: OpenCatalogA"

  def ParseDate(self, ctx):
    locale = ctx.cpu.r_reg(REG_A0)
    date = ctx.cpu.r_reg(REG_A1)
    fmtTemplate = ctx.cpu.r_reg(REG_A2)
    putCharFunc = ctx.cpu.r_reg(REG_A3)
    print "not implemented: ParseDate"
  
  def StrConvert(self, ctx):
    locale = ctx.cpu.r_reg(REG_A0)
    string = ctx.cpu.r_reg(REG_A1)
    buffer = ctx.cpu.r_reg(REG_A2)
    bufferSize = ctx.cpu.r_reg(REG_D0)
    type = ctx.cpu.r_reg(REG_D1)
    print "not implemented: StrConvert"

  def StrnCmp(self, ctx):
    locale = ctx.cpu.r_reg(REG_A0)
    string1 = ctx.cpu.r_reg(REG_A1)
    string2 = ctx.cpu.r_reg(REG_A2)
    length = ctx.cpu.r_reg(REG_D0)
    type = ctx.cpu.r_reg(REG_D1)
    print "not implemented: StrnCmp"
"""
