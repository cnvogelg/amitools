from amitools.vamos.libstructs import IORequestStruct, NodeType, TimeRequestStruct
from amitools.vamos.libtypes import ExecLibrary as ExecLibraryType

TR_GETSYSTIME = 11


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


def pytask_exec_timer_io_test(vamos_task):
    def task(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        port = exec_proxy.CreateMsgPort()
        size = TimeRequestStruct.get_byte_size()
        req_addr = exec_proxy.CreateIORequest(port, size)
        io = IORequestStruct(ctx.mem, req_addr)
        req = TimeRequestStruct(ctx.mem, req_addr)

        assert exec_proxy.OpenDevice("timer.device", 0, req_addr, 0) == 0

        io.command.val = TR_GETSYSTIME
        req.tr_time.tv_secs.val = 0
        req.tr_time.tv_micro.val = 0

        assert exec_proxy.DoIO(req_addr) == 0
        assert exec_proxy.CheckIO(req_addr) == req_addr
        assert io.error.val == 0
        assert io.message.node.type.val == NodeType.NT_REPLYMSG
        assert req.tr_time.tv_secs.val > 0

        sig_mask = 1 << port.sig_bit.val
        exec_proxy.SetSignal(0, sig_mask)
        req.tr_time.tv_secs.val = 0
        req.tr_time.tv_micro.val = 0

        assert exec_proxy.SendIO(req_addr) == 0
        assert exec_proxy.CheckIO(req_addr) == req_addr
        assert exec_proxy.SetSignal(0, 0) & sig_mask == sig_mask
        assert exec_proxy.WaitIO(req_addr) == 0
        assert exec_proxy.GetMsg(port) is None
        assert req.tr_time.tv_secs.val > 0

        exec_proxy.CloseDevice(req_addr)
        exec_proxy.DeleteIORequest(req_addr)
        exec_proxy.DeleteMsgPort(port)
        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_input_device_test(vamos_task):
    def task(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        port = exec_proxy.CreateMsgPort()
        size = TimeRequestStruct.get_byte_size()
        req_addr = exec_proxy.CreateIORequest(port, size)
        req = IORequestStruct(ctx.mem, req_addr)

        assert exec_proxy.OpenDevice("input.device", 0, req_addr, 0) == 0
        assert req.device.aptr != 0
        assert exec_proxy.DoIO(req_addr) == 0
        assert req.error.val == 0

        exec_proxy.CloseDevice(req_addr)
        assert req.device.aptr == 0
        exec_proxy.DeleteIORequest(req_addr)
        exec_proxy.DeleteMsgPort(port)
        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_create_io_request_test(vamos_task):
    def task(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        port = exec_proxy.CreateMsgPort()
        size = TimeRequestStruct.get_byte_size()
        req_addr = exec_proxy.CreateIORequest(port, size)
        req = IORequestStruct(ctx.mem, req_addr)

        assert req.message.reply_port.aptr == port.addr
        assert req.message.length.val == size
        assert req.flags.val == 0
        assert req.error.val == 0

        exec_proxy.DeleteIORequest(req_addr)
        exec_proxy.DeleteMsgPort(port)
        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]
