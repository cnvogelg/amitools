from amitools.vamos.libstructs import NodeStruct, NodeType
from amitools.vamos.libtypes import ExecLibrary as ExecLibraryType, Node


def pytask_exec_add_rem_resource_test(vamos_task):
    def task(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        exec_base = ExecLibraryType(ctx.mem, exec_proxy.base_addr)

        node_mem = ctx.alloc.alloc_struct(NodeStruct)
        resource = Node(ctx.mem, node_mem.addr)
        name_mem = ctx.alloc.alloc_cstr("my.resource", label="resname")
        resource.name.aptr = name_mem.addr

        exec_proxy.AddResource(resource)
        node = exec_base.resource_list.find_name("my.resource")
        assert node is not None
        assert node.type.val == NodeType.NT_RESOURCE

        exec_proxy.RemResource(resource)
        assert exec_base.resource_list.find_name("my.resource") is None

        ctx.alloc.free_cstr(name_mem)
        ctx.alloc.free_struct(node_mem)
        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]
