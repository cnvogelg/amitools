from amitools.vamos.log import log_exec

from .supervisor import run_supervisor


class MiscMixin:
    """exec.library misc LVOs (fd banner: misc)."""

    def Supervisor(self, ctx):
        return run_supervisor(ctx)

    def Alert(self, ctx, code):
        log_exec.error("ALERT: code=%08x", code)
