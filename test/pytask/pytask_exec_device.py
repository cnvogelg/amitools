from amitools.vamos.astructs import AccessStruct
from amitools.vamos.libstructs import IORequestStruct, NodeType, TimeRequestStruct
from amitools.vamos.libtypes import ExecLibrary as ExecLibraryType


def pytask_exec_base_lists_test(vamos_task):
    def task(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        exec_base = ExecLibraryType(ctx.mem, exec_proxy.base_addr)

        assert exec_base.mem_list.type.val == NodeType.NT_MEMORY
        assert exec_base.mem_list.is_empty()
        assert exec_base.resource_list.type.val == NodeType.NT_RESOURCE
        assert exec_base.resource_list.is_empty()
        assert exec_base.device_list.type.val == NodeType.NT_DEVICE
        assert exec_base.device_list.is_empty()
        assert exec_base.intr_list.type.val == NodeType.NT_INTERRUPT
        assert exec_base.intr_list.is_empty()
        assert exec_base.lib_list.type.val == NodeType.NT_LIBRARY
        assert exec_base.port_list.type.val == NodeType.NT_MSGPORT
        assert exec_base.port_list.is_empty()
        assert exec_base.task_ready.type.val == NodeType.NT_TASK
        assert exec_base.task_wait.type.val == NodeType.NT_TASK
        assert exec_base.semaphore_list.type.val == NodeType.NT_SEMAPHORE
        assert exec_base.semaphore_list.is_empty()
        assert exec_base.mem_handlers.is_empty()

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_create_io_request_test(vamos_task):
    def task(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        port = exec_proxy.CreateMsgPort()
        size = TimeRequestStruct.get_byte_size()
        req_addr = exec_proxy.CreateIORequest(port, size)
        req = AccessStruct(ctx.mem, IORequestStruct, req_addr)

        assert req.r_s("io_Message.mn_ReplyPort") == port.addr
        assert req.r_s("io_Message.mn_Length") == size
        assert req.r_s("io_Flags") == 0
        assert req.r_s("io_Error") == 0

        exec_proxy.DeleteIORequest(req_addr)
        exec_proxy.DeleteMsgPort(port)
        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]
