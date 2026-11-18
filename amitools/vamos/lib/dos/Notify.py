"""dos.library notification requests (RKRM AmigaDOS 3, StartNotify and
EndNotify).

Vamos has no file system notifier yet. StartNotify/EndNotify are harmless
no-ops: they remember which request objects are active and succeed, so
programs that only register/unregister a request keep working.
"""

from amitools.vamos.log import log_dos

from .Error import DOSFALSE, DOSTRUE, ERROR_REQUIRED_ARG_MISSING


class NotifyHelper:
    def __init__(self):
        self.active = set()

    def start_notify(self, ctx, notify):
        if notify == 0:
            return DOSFALSE, ERROR_REQUIRED_ARG_MISSING
        self.active.add(notify)
        log_dos.info("StartNotify(%06x): no-op", notify)
        return DOSTRUE, 0

    def end_notify(self, ctx, notify):
        if notify == 0:
            return DOSFALSE, ERROR_REQUIRED_ARG_MISSING
        self.active.discard(notify)
        log_dos.info("EndNotify(%06x): no-op", notify)
        return DOSTRUE, 0
