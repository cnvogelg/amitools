from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.log import log_main


class IntuitionLibrary(LibImpl):
    def DisplayAlert(self, ctx):
        alert_num = ctx.cpu.r_reg(REG_D0)
        msg_ptr = ctx.cpu.r_reg(REG_A0)
        msg = ctx.mem.r_cstr(msg_ptr)
        log_main.error(
            "-----> DisplayAlert: #%08x - '%s'@%08x <-----", alert_num, msg, msg_ptr
        )

    def AutoRequest(self, ctx):
        IntuiText = ctx.cpu.r_reg(REG_A1)
        IText = ctx.mem.r32(IntuiText + 12)  # IntuiText.ITexT
        msg = ctx.mem.r_cstr(IText)
        log_main.error("-----> AutoRequest '%s'", msg)

    def EasyRequestArgs(self, ctx):
        EasyStruct = ctx.cpu.r_reg(REG_A1)
        es_TextFormat = ctx.mem.r32(EasyStruct + 12)  # EasyStruct.es_TextFormat
        msg = ctx.mem.r_cstr(es_TextFormat)
        log_main.error("-----> EasyRequest '%s'", msg)
