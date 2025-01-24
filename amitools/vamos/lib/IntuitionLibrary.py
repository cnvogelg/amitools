from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.log import log_intuition
from amitools.vamos.lib.TimerDevice import TimerDevice


class IntuitionLibrary(LibImpl):
    def DisplayAlert(self, ctx, alert_num, msg_ptr):
        msg = ctx.mem.r_cstr(msg_ptr)
        log_intuition.error(
            "-----> DisplayAlert: #%08x - '%s'@%08x <-----", alert_num, msg, msg_ptr
        )

    def AutoRequest(self, ctx, text):
        itext = ctx.mem.r32(text + 12)  # IntuiText.ITexT
        msg = ctx.mem.r_cstr(itext)
        log_intuition.error("-----> AutoRequest '%s'", msg)

    def EasyRequestArgs(self, ctx, easy_struct):
        es_TextFormat = ctx.mem.r32(easy_struct + 12)  # EasyStruct.es_TextFormat
        msg = ctx.mem.r_cstr(es_TextFormat)
        log_intuition.error("-----> EasyRequest '%s'", msg)

    def CurrentTime(self, ctx, secs_ptr, micros_ptr):
        secs, micros = TimerDevice.get_sys_time()
        log_intuition.info(
            "CurrentTime(%08x, %08x) -> secs=%d micros=%d",
            secs_ptr,
            micros_ptr,
            secs,
            micros,
        )
        ctx.mem.w32(secs_ptr, secs)
        ctx.mem.w32(micros_ptr, micros)
