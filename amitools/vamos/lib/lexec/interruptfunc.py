from amitools.vamos.log import log_exec

from .funcbase import FuncBaseMixin


class InterruptMixin(FuncBaseMixin):
    """exec.library interrupt-control LVOs (fd banner: interrupts)."""

    def Disable(self, ctx):
        # map disable to forbid for now
        # (since we do not deal with irqs right now)
        log_exec.info("Disable -> Forbid")
        self.forbid()

    def Enable(self, ctx):
        # map enable to permit for now
        # (since we do not deal with irqs right now)
        log_exec.info("Enable -> Permit")
        self.permit()

    def Forbid(self, ctx):
        self.forbid()

    def Permit(self, ctx):
        self.permit()

    def Cause(self, ctx, interrupt):
        self.soft_int.cause(interrupt)
