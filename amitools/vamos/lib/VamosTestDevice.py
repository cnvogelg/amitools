from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.error import *


class VamosTestDevice(LibImpl):
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

    def BeginIO(self, ctx):
        print("VamosTest: BeginIO")

    def AbortIO(self, ctx):
        print("VamosTest: AbortIO")

    def Add(self, ctx):
        a = ctx.cpu.r_reg(REG_D0)
        b = ctx.cpu.r_reg(REG_D1)
        return a + b
