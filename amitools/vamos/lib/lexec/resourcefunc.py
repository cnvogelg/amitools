from amitools.vamos.libstructs import NodeType
from amitools.vamos.libtypes import Node
from amitools.vamos.log import log_exec
from amitools.vamos.machine.regs import REG_A1


class ResourceMixin:
    """exec.library resource LVOs (fd banner: resources)."""

    def AddResource(self, ctx, resource: Node):
        """add a resource to the public resource list (bookkeeping only)."""
        resource.type.val = NodeType.NT_RESOURCE
        self.exec_lib.resource_list.enqueue(resource)
        log_exec.info("AddResource(%s)", resource)

    def RemResource(self, ctx, resource: Node):
        log_exec.info("RemResource(%s)", resource)
        resource.remove()

    def OpenResource(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_A1)
        name = ctx.mem.r_cstr(name_ptr)
        log_exec.info("OpenResource(%s) ignored" % name)
        return 0
