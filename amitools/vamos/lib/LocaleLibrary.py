from amitools.vamos.libcore import LibImpl
import string
from amitools.vamos.machine.regs import REG_A0, REG_D0

class LocaleLibrary(LibImpl):

    def OpenLocale(self, ctx):
        self.name = ctx.cpu.r_reg(REG_A0)
        # dummy
        return 1

    def CloseLocale(self, ctx):
        self.locale = ctx.cpu.r_reg(REG_A0)
        # dummy - accept all

    def IsUpper(self, ctx):
        self.locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.ascii_uppercase

    def IsLower(self, ctx):
        self.locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.ascii_lowercase

    def IsDigit(self, ctx):
        self.locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.digits

    def IsPrint(self, ctx):
        self.locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.printable

    def IsCntrl(self, ctx):
        self.locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        # maybe not ok...
        return character < 32 and not chr(character) in string.printable

    def IsXDigit(self, ctx):
        self.locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.hexdigits

    def IsSpace(self, ctx):
        self.locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.whitespace

    def IsPunct(self, ctx):
        self.locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.punctuation

    def IsGraph(self, ctx):
        self.locale = ctx.cpu.r_reg(REG_A0)
        character = ctx.cpu.r_reg(REG_D0)
        return chr(character) in string.printable and not chr(character) in string.whitespace

