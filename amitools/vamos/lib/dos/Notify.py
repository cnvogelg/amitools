"""dos.library notification requests (RKRM AmigaDOS 3, StartNotify and
EndNotify).

The request's name is resolved through the handler manager and the packet is
delivered to the responsible handler (ACTION_ADD_NOTIFY / ACTION_REMOVE_NOTIFY).
Every file system handler accepts it as a no-op success, so the observable
behaviour is unchanged; a request whose name does not resolve also keeps the
previous no-op success (AmigaDOS only notifies an existing object).
"""

from amitools.vamos.astructs import LONG
from amitools.vamos.handler import HandlerError
from amitools.vamos.libstructs import NotifyRequestStruct
from amitools.vamos.log import log_dos

from . import Helper
from .Error import DOSFALSE, DOSTRUE, ERROR_REQUIRED_ARG_MISSING


def _read_name(ctx, notify):
    """read the request's ``nr_Name`` (or ``""`` if it cannot be read)"""
    try:
        request = NotifyRequestStruct(ctx.mem, notify)
        bptr = request.nr_Name.bptr
        if not bptr:
            return ""
        return ctx.mem.r_bstr(bptr << 2)
    except Exception:
        return ""


def _notify(dos, ctx, notify, start):
    name = _read_name(ctx, notify)
    if name and dos.handler_mgr is not None:
        cwd = dos.get_cwd_path(ctx)
        try:
            if start:
                dos.handler_mgr.add_notify(name, notify, cwd=cwd)
            else:
                dos.handler_mgr.remove_notify(name, notify, cwd=cwd)
        except HandlerError as e:
            # an unresolved object keeps the previous no-op success
            log_dos.info("notify '%s': %s", name, e)
    verb = "StartNotify" if start else "EndNotify"
    log_dos.info("%s(%06x, '%s'): no-op", verb, notify, name)
    return DOSTRUE, 0


def start_notify(dos, ctx, notify):
    if notify == 0:
        return DOSFALSE, ERROR_REQUIRED_ARG_MISSING
    return _notify(dos, ctx, notify, True)


def end_notify(dos, ctx, notify):
    if notify == 0:
        return DOSFALSE, ERROR_REQUIRED_ARG_MISSING
    return _notify(dos, ctx, notify, False)


class NotifyMixin:
    """dos.library fd methods (HANDLER.md step 22m)."""

    def StartNotify(self, ctx, notify: LONG):
        ok, err = start_notify(self, ctx, notify.val)
        return Helper.bool_result(self, ctx, ok, err)

    def EndNotify(self, ctx, notify: LONG):
        ok, err = end_notify(self, ctx, notify.val)
        return Helper.bool_result(self, ctx, ok, err)
