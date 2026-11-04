from amitools.vamos.libstructs import (
    MsgPortFlags,
    MsgPortStruct,
    NodeType,
    ProcessStruct,
    TaskState,
)
from amitools.vamos.libtypes import DosTag, TagList
from amitools.vamos.loader import SegList
from amitools.vamos.machine.opcodes import op_rts

LVO_SIGNAL = -324
CHILD_CODE_SIZE = 32


def write_child_code(mem, pc, exec_base, task_addr, sig_mask):
    """child code: Signal(task, sig_mask) through exec, then return 42"""
    mem.w16(pc, 0x2C7C)  # movea.l #exec_base,a6
    mem.w32(pc + 2, exec_base)
    mem.w16(pc + 6, 0x227C)  # movea.l #task,a1
    mem.w32(pc + 8, task_addr)
    mem.w16(pc + 12, 0x203C)  # move.l #sig_mask,d0
    mem.w32(pc + 14, sig_mask)
    mem.w16(pc + 18, 0x4EAE)  # jsr Signal(a6)
    mem.w16(pc + 20, LVO_SIGNAL & 0xFFFF)
    mem.w16(pc + 22, 0x702A)  # moveq #42,d0
    mem.w16(pc + 24, op_rts)


def wait_for_child(task, exec_proxy, sig_mask, name):
    """wait for the child's signal, then let it run until it is gone"""
    assert exec_proxy.Wait(sig_mask) == sig_mask
    while task.find_task(name) is not None:
        task.reschedule()


def pytask_dos_create_new_proc_entry_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        mem = ctx.mem

        parent = ProcessStruct(mem, ctx.process.proc.addr)
        exec_base = ctx.exec_lib.exec_lib.addr
        sig = exec_proxy.AllocSignal(-1)
        sig_mask = 1 << sig
        code = ctx.alloc.alloc_memory(CHILD_CODE_SIZE, label="child_code")
        write_child_code(mem, code.addr, exec_base, parent.addr, sig_mask)
        name_mem = ctx.alloc.alloc_cstr("child_entry")
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_Entry, code.addr),
            (DosTag.NP_Name, name_mem.addr),
            (DosTag.NP_StackSize, 8192),
            (DosTag.NP_Priority, 7),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        child = ProcessStruct(mem, proc_addr)
        port_addr = child.msg_port.addr
        port = MsgPortStruct(mem, port_addr)
        child_task = task.find_task("child_entry")
        assert child_task is not None

        assert child.task.node.type.val == NodeType.NT_PROCESS
        assert child.task.node.name.str == "child_entry"
        assert child.task.node.pri.val == 7
        assert child.task.state.val == TaskState.TS_READY
        assert child.stack_size.val == 8192
        assert child.task.sp_lower.aptr != 0
        assert child.task.sp_upper.aptr == child.task.sp_lower.aptr + 8192
        assert child.task.sp_reg.aptr == child.task.sp_upper.aptr - 4
        assert child.task.sig_alloc.val & (1 << 8)
        assert child.cis.bptr == parent.cis.bptr
        assert child.cos.bptr == parent.cos.bptr
        assert port.flags.val == MsgPortFlags.PA_SIGNAL
        assert port.sig_bit.val == 8
        assert port.sig_task.aptr == proc_addr
        assert ctx.exec_lib.port_mgr.has_port(port_addr)
        # the process port is no public port
        assert exec_proxy.FindPort("child_entry") is None

        # the child runs beside us, signals us and ends. then it is freed
        wait_for_child(task, exec_proxy, sig_mask, "child_entry")
        assert child_task.get_exit_code() == 42
        assert not ctx.exec_lib.port_mgr.has_port(port_addr)

        exec_proxy.FreeSignal(sig)
        tags.free()
        ctx.alloc.free_cstr(name_mem)
        ctx.alloc.free_memory(code)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_seglist_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        mem = ctx.mem

        parent = ProcessStruct(mem, ctx.process.proc.addr)
        exec_base = ctx.exec_lib.exec_lib.addr
        sig = exec_proxy.AllocSignal(-1)
        sig_mask = 1 << sig
        seg_list = SegList.alloc(ctx.alloc, [CHILD_CODE_SIZE])
        write_child_code(mem, seg_list.get_start_pc(), exec_base, parent.addr, sig_mask)
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_SegList, seg_list.get_baddr()),
            (DosTag.NP_StackSize, 4096),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        child = ProcessStruct(mem, proc_addr)
        child_task = task.find_task("child_process")
        assert child_task is not None

        assert child.task.node.name.str == "child_process"
        assert child.seg_list.bptr == seg_list.get_baddr()
        assert child.stack_size.val == 4096

        # the child starts at the first segment and ends
        wait_for_child(task, exec_proxy, sig_mask, "child_process")
        assert child_task.get_exit_code() == 42

        # the seglist stays with the parent: NP_FreeSeglist is not honored
        seg_list.free()
        exec_proxy.FreeSignal(sig)
        tags.free()
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_no_entry_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()

        tags = TagList.alloc(ctx.alloc, (DosTag.NP_StackSize, 4096))
        assert dos_proxy.CreateNewProc(tags) == 0
        assert task.find_task("child_process") is None

        tags.free()
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]
