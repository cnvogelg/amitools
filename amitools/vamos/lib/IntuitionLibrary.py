from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.log import log_intuition
from amitools.vamos.lib.TimerDevice import TimerDevice


class IntuitionLibrary(LibImpl):
    # Text and gadgets of the last EasyRequest answered with its first gadget.
    _easy_last = None

    def DisplayAlert(self, ctx, alert_num, msg_ptr):
        msg = ctx.mem.r_cstr(msg_ptr)
        log_intuition.error(
            "-----> DisplayAlert: #%08x - '%s'@%08x <-----", alert_num, msg, msg_ptr
        )

    def AutoRequest(self, ctx, text):
        itext = ctx.mem.r32(text + 12)  # IntuiText.ITexT
        msg = ctx.mem.r_cstr(itext)
        log_intuition.error("-----> AutoRequest '%s'", msg)

    def EasyRequestArgs(self, ctx, window, easy_struct, idcmp_ptr, args):
        mem = ctx.mem
        msg = mem.r_cstr(mem.r32(easy_struct + 12))  # EasyStruct.es_TextFormat
        gad_ptr = mem.r32(easy_struct + 16)  # EasyStruct.es_GadgetFormat
        gadgets = mem.r_cstr(gad_ptr) if gad_ptr else ""
        key = (msg, gadgets)
        # No user can answer. Take the first gadget once, so that e.g. SFS
        # startup can continue, then the rightmost (0, e.g. CANCEL) while
        # the same requester repeats, so RETRY|CANCEL requesters cannot loop.
        if self._easy_last == key:
            log_intuition.debug("EasyRequest '%s' [%s] repeated -> 0", msg, gadgets)
            return 0
        self._easy_last = key
        log_intuition.error("-----> EasyRequest '%s' [%s] -> 1", msg, gadgets)
        return 1

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
