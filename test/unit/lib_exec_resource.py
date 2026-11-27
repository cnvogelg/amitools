from amitools.vamos.lib.lexec.resourcefunc import ResourceMixin
from amitools.vamos.libstructs import NodeStruct, NodeType
from amitools.vamos.libtypes import Node
from lib_exec_helper import ExecHost, make_exec_lib


class Host(ExecHost, ResourceMixin):
    pass


def exec_add_rem_resource_test():
    mem, alloc, el = make_exec_lib()
    host = Host(mem, alloc, el)
    node_struct = alloc.alloc_astruct(NodeStruct, label="resource")
    resource = Node(mem, node_struct.addr)
    host.AddResource(host.ctx, resource)
    node = host.exec_lib.resource_list.get_head()
    assert node.addr == resource.addr
    assert node.type.val == NodeType.NT_RESOURCE
    host.RemResource(host.ctx, resource)
    assert host.exec_lib.resource_list.is_empty()
