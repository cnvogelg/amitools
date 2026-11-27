from amitools.vamos.log import log_exec
from amitools.vamos.machine.regs import REG_A1


class ResourceMixin:
    """exec.library resource LVOs (fd banner: resources)."""

    def OpenResource(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_A1)
        name = ctx.mem.r_cstr(name_ptr)
        log_exec.info("OpenResource(%s) ignored" % name)
        return 0
