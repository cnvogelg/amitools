from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import (
    MsgPortFlags,
    MsgPortStruct,
    NodeType,
    ProcessStruct,
    TaskState,
)
from amitools.vamos.libtypes import DosTag, TagList


def pytask_dos_create_new_proc_entry_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()

        parent = ProcessStruct(ctx.mem, ctx.process.proc.addr)
        name_mem = ctx.alloc.alloc_cstr("child_entry")
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_Entry, 0x123456),
            (DosTag.NP_Name, name_mem.addr),
            (DosTag.NP_StackSize, 8192),
            (DosTag.NP_Priority, 7),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        child = ProcessStruct(ctx.mem, proc_addr)
        port_addr = child.msg_port.addr
        port = MsgPortStruct(ctx.mem, port_addr)

        assert proc_addr != 0
        assert child.task.node.type.val == NodeType.NT_PROCESS
        assert child.task.node.name.str == "child_entry"
        assert child.task.node.pri.val == 7
        assert child.task.state.val == TaskState.TS_READY
        assert child.stack_size.val == 8192
        assert child.task.sp_reg.aptr != 0
        assert child.task.sp_lower.aptr != 0
        assert child.task.sp_upper.aptr != 0
        assert child.cis.bptr == parent.cis.bptr
        assert child.cos.bptr == parent.cos.bptr
        assert port.flags.val == MsgPortFlags.PA_SIGNAL
        assert port.sig_bit.val == 8
        assert port.sig_task.aptr == proc_addr
        assert port.node.name.str == "child_entry"
        assert ctx.exec_lib.port_mgr.has_port(port_addr)
        assert DosLibrary._child_processes[proc_addr]["entry_pc"] == 0x123456

        DosLibrary._child_processes.pop(proc_addr, None)
        tags.free()
        ctx.alloc.free_cstr(name_mem)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_seglist_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()

        seglist_bptr = 0x3456
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_SegList, seglist_bptr),
            (DosTag.NP_StackSize, 4096),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        assert (
            DosLibrary._child_processes[proc_addr]["entry_pc"]
            == (seglist_bptr << 2) + 4
        )

        DosLibrary._child_processes.pop(proc_addr, None)
        tags.free()
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]
