from amitools.vamos.libstructs import (
    MsgPortFlags,
    MsgPortStruct,
    NodeType,
    ProcessFlags,
    ProcessStruct,
    TaskState,
)
from amitools.vamos.libtypes import DosTag, TagList
from amitools.vamos.lib.dos.Error import DOSTRUE
from amitools.vamos.loader import SegList
from amitools.vamos.loader.segload import SegLoadInfo
from amitools.vamos.machine.opcodes import op_rts

LVO_SIGNAL = -324
CHILD_CODE_SIZE = 32
SIGF_CHILD = 1 << 1

# dos.library LVOs used by the redirection child code
LVO_READ = -42
LVO_WRITE = -48
LVO_INPUT = -54
LVO_OUTPUT = -60
REDIR_CODE_SIZE = 64


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


def write_child_exit_code(mem, pc, code=42):
    """child code: return ``code`` immediately"""
    mem.w16(pc, 0x7000 | (code & 0xFF))  # moveq #code,d0
    mem.w16(pc + 2, op_rts)


def write_args_child_code(mem, pc, exec_base, task_addr, sig_mask, scratch):
    """child code: save A0/D0 to ``scratch``, Signal(parent), then return 42"""
    mem.w16(pc, 0x23C0)  # move.l d0,(scratch).l
    mem.w32(pc + 2, scratch)
    mem.w16(pc + 6, 0x23C8)  # move.l a0,(scratch+4).l
    mem.w32(pc + 8, scratch + 4)
    mem.w16(pc + 12, 0x2C7C)  # movea.l #exec_base,a6
    mem.w32(pc + 14, exec_base)
    mem.w16(pc + 18, 0x227C)  # movea.l #task,a1
    mem.w32(pc + 20, task_addr)
    mem.w16(pc + 24, 0x203C)  # move.l #sig_mask,d0
    mem.w32(pc + 26, sig_mask)
    mem.w16(pc + 30, 0x4EAE)  # jsr Signal(a6)
    mem.w16(pc + 32, LVO_SIGNAL & 0xFFFF)
    mem.w16(pc + 34, 0x702A)  # moveq #42,d0
    mem.w16(pc + 36, op_rts)


def write_exit_handler(mem, pc, scratch_addr):
    """NP_ExitCode handler: store D0 (rc) and D1 (exit data), then return"""
    mem.w16(pc, 0x23C0)  # move.l d0,(scratch).l
    mem.w32(pc + 2, scratch_addr)
    mem.w16(pc + 6, 0x23C1)  # move.l d1,(scratch+4).l
    mem.w32(pc + 8, scratch_addr + 4)
    mem.w16(pc + 12, op_rts)


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
        # NP_Input/NP_Output default to NIL: opens; NP_Error defaults to ZERO
        # (RKRM). Input/output are closed on exit, error is not.
        assert child.cis.bptr != 0
        assert child.cos.bptr != 0
        assert child.ces.bptr == 0
        assert child.cis.bptr != parent.cis.bptr
        assert child.flags.val & ProcessFlags.PRF_CLOSEINPUT
        assert child.flags.val & ProcessFlags.PRF_CLOSEOUTPUT
        assert not (child.flags.val & ProcessFlags.PRF_CLOSEERROR)
        fm = ctx.dos_lib.file_mgr
        assert fm.get_by_b_addr(child.cis.bptr).is_nil
        assert fm.get_by_b_addr(child.cos.bptr).is_nil
        cis_b, cos_b = child.cis.bptr, child.cos.bptr
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
        # the NIL: handles were closed on exit
        assert cis_b not in fm.files_by_b_addr
        assert cos_b not in fm.files_by_b_addr

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
        # no NP_Name: the RKRM default name is used
        child_task = task.find_task("New Process")
        assert child_task is not None

        assert child.task.node.name.str == "New Process"
        assert child.seg_list.bptr == seg_list.get_baddr()
        assert child.stack_size.val == 4096

        # the child starts at the first segment and ends
        wait_for_child(task, exec_proxy, sig_mask, "New Process")
        assert child_task.get_exit_code() == 42

        # a seglist DOS does not manage is not freed (NP_FreeSegList)
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
        assert task.find_task("New Process") is None

        tags.free()
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_defaults_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        mem = ctx.mem
        lock_mgr = ctx.dos_lib.lock_mgr

        parent = ProcessStruct(mem, ctx.process.proc.addr)
        # give the parent non-default values to inherit: a priority and real
        # current/home dir locks
        parent.task.node.pri.val = 3
        cwd_lock = lock_mgr.create_lock(None, "root:", False)
        home_lock = lock_mgr.create_lock(None, "root:", False)
        parent.current_dir.bptr = cwd_lock.b_addr
        parent.home_dir.bptr = home_lock.b_addr
        exec_base = ctx.exec_lib.exec_lib.addr
        sig = exec_proxy.AllocSignal(-1)
        sig_mask = 1 << sig
        code = ctx.alloc.alloc_memory(CHILD_CODE_SIZE, label="child_code")
        write_child_code(mem, code.addr, exec_base, parent.addr, sig_mask)
        tags = TagList.alloc(ctx.alloc, (DosTag.NP_Entry, code.addr))

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        child = ProcessStruct(mem, proc_addr)
        child_task = task.find_task("New Process")
        assert child_task is not None

        # RKRM defaults: name "New Process", stack 4000, priority 0
        assert child.task.node.name.str == "New Process"
        assert child.stack_size.val == 4000
        assert child.task.node.pri.val == 0
        # absent dir tags: the child gets *duplicated* locks (distinct BPTRs
        # pointing at the same object), not the caller's locks
        assert child.current_dir.bptr != 0
        assert child.current_dir.bptr != cwd_lock.b_addr
        assert child.home_dir.bptr != 0
        assert child.home_dir.bptr != home_lock.b_addr
        assert child.flags.val & ProcessFlags.PRF_FREECURRDIR
        child_cwd = lock_mgr.get_by_b_addr(child.current_dir.bptr)
        child_home = lock_mgr.get_by_b_addr(child.home_dir.bptr)
        assert child_cwd is not cwd_lock
        assert lock_mgr.same_lock(child_cwd, cwd_lock)
        assert lock_mgr.same_lock(child_home, home_lock)
        cwd_key = lock_mgr.keys[cwd_lock.key]
        child_cwd_bptr = child.current_dir.bptr
        child_home_bptr = child.home_dir.bptr

        wait_for_child(task, exec_proxy, sig_mask, "New Process")

        # the child's duplicated locks are released on exit ...
        assert child_cwd_bptr not in cwd_key.locks_by_baddr
        assert child_home_bptr not in cwd_key.locks_by_baddr
        # ... while the caller's locks are still valid
        assert lock_mgr.get_by_b_addr(cwd_lock.b_addr) is cwd_lock
        assert lock_mgr.get_by_b_addr(home_lock.b_addr) is home_lock

        parent.current_dir.bptr = 0
        parent.home_dir.bptr = 0
        lock_mgr.release_lock(cwd_lock)
        lock_mgr.release_lock(home_lock)
        exec_proxy.FreeSignal(sig)
        tags.free()
        ctx.alloc.free_memory(code)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_explicit_dirs_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        mem = ctx.mem
        lock_mgr = ctx.dos_lib.lock_mgr

        parent = ProcessStruct(mem, ctx.process.proc.addr)
        exec_base = ctx.exec_lib.exec_lib.addr
        sig = exec_proxy.AllocSignal(-1)
        sig_mask = 1 << sig
        code = ctx.alloc.alloc_memory(CHILD_CODE_SIZE, label="child_code")
        write_child_code(mem, code.addr, exec_base, parent.addr, sig_mask)
        name = ctx.alloc.alloc_cstr("dirs_child")
        cwd_lock = lock_mgr.create_lock(None, "root:", False)
        home_lock = lock_mgr.create_lock(None, "ram:", False)
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_Entry, code.addr),
            (DosTag.NP_Name, name.addr),
            (DosTag.NP_CurrentDir, cwd_lock.b_addr),
            (DosTag.NP_HomeDir, home_lock.b_addr),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        child = ProcessStruct(mem, proc_addr)
        # an explicit tag lock is absorbed by the child as-is
        assert child.current_dir.bptr == cwd_lock.b_addr
        assert child.home_dir.bptr == home_lock.b_addr
        assert child.flags.val & ProcessFlags.PRF_FREECURRDIR
        cwd_key = lock_mgr.keys[cwd_lock.key]
        home_key = lock_mgr.keys[home_lock.key]
        cwd_bptr = cwd_lock.b_addr
        home_bptr = home_lock.b_addr

        wait_for_child(task, exec_proxy, sig_mask, "dirs_child")

        # both provided locks are released when the child exits
        assert cwd_bptr not in cwd_key.locks_by_baddr
        assert home_bptr not in home_key.locks_by_baddr

        exec_proxy.FreeSignal(sig)
        tags.free()
        ctx.alloc.free_cstr(name)
        ctx.alloc.free_memory(code)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_explicit_handles_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        mem = ctx.mem
        fm = ctx.dos_lib.file_mgr

        parent = ProcessStruct(mem, ctx.process.proc.addr)
        exec_base = ctx.exec_lib.exec_lib.addr
        sig = exec_proxy.AllocSignal(-1)
        sig_mask = 1 << sig
        code = ctx.alloc.alloc_memory(CHILD_CODE_SIZE, label="child_code")
        write_child_code(mem, code.addr, exec_base, parent.addr, sig_mask)
        name = ctx.alloc.alloc_cstr("handles_child")
        # caller supplied handles: input/output closed on exit by default,
        # the error handle is not (RKRM)
        in_fh = fm.open(None, "NIL:", "r")
        out_fh = fm.open(None, "NIL:", "w")
        err_fh = fm.open(None, "NIL:", "w")
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_Entry, code.addr),
            (DosTag.NP_Name, name.addr),
            (DosTag.NP_Input, in_fh.b_addr),
            (DosTag.NP_Output, out_fh.b_addr),
            (DosTag.NP_Error, err_fh.b_addr),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        child = ProcessStruct(mem, proc_addr)
        assert child.cis.bptr == in_fh.b_addr
        assert child.cos.bptr == out_fh.b_addr
        assert child.ces.bptr == err_fh.b_addr
        assert child.flags.val & ProcessFlags.PRF_CLOSEINPUT
        assert child.flags.val & ProcessFlags.PRF_CLOSEOUTPUT
        assert not (child.flags.val & ProcessFlags.PRF_CLOSEERROR)

        wait_for_child(task, exec_proxy, sig_mask, "handles_child")
        # input/output were closed on exit, the error handle stays open
        assert in_fh.b_addr not in fm.files_by_b_addr
        assert out_fh.b_addr not in fm.files_by_b_addr
        assert err_fh.b_addr in fm.files_by_b_addr

        fm.close(err_fh)
        exec_proxy.FreeSignal(sig)
        tags.free()
        ctx.alloc.free_cstr(name)
        ctx.alloc.free_memory(code)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_keep_handles_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        mem = ctx.mem
        fm = ctx.dos_lib.file_mgr

        parent = ProcessStruct(mem, ctx.process.proc.addr)
        exec_base = ctx.exec_lib.exec_lib.addr
        sig = exec_proxy.AllocSignal(-1)
        sig_mask = 1 << sig
        code = ctx.alloc.alloc_memory(CHILD_CODE_SIZE, label="child_code")
        write_child_code(mem, code.addr, exec_base, parent.addr, sig_mask)
        name = ctx.alloc.alloc_cstr("keep_child")
        in_fh = fm.open(None, "NIL:", "r")
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_Entry, code.addr),
            (DosTag.NP_Name, name.addr),
            (DosTag.NP_Input, in_fh.b_addr),
            (DosTag.NP_CloseInput, 0),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        child = ProcessStruct(mem, proc_addr)
        assert not (child.flags.val & ProcessFlags.PRF_CLOSEINPUT)

        wait_for_child(task, exec_proxy, sig_mask, "keep_child")
        # NP_CloseInput=FALSE: the caller keeps the handle
        assert in_fh.b_addr in fm.files_by_b_addr

        fm.close(in_fh)
        exec_proxy.FreeSignal(sig)
        tags.free()
        ctx.alloc.free_cstr(name)
        ctx.alloc.free_memory(code)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_arguments_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        mem = ctx.mem
        fm = ctx.dos_lib.file_mgr

        parent = ProcessStruct(mem, ctx.process.proc.addr)
        exec_base = ctx.exec_lib.exec_lib.addr
        sig = exec_proxy.AllocSignal(-1)
        sig_mask = 1 << sig
        code = ctx.alloc.alloc_memory(CHILD_CODE_SIZE, label="child_code")
        write_child_code(mem, code.addr, exec_base, parent.addr, sig_mask)
        name = ctx.alloc.alloc_cstr("args_child")
        args = ctx.alloc.alloc_cstr("arg1 arg2")
        in_fh = fm.open(None, "NIL:", "r")
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_Entry, code.addr),
            (DosTag.NP_Name, name.addr),
            (DosTag.NP_Input, in_fh.b_addr),
            (DosTag.NP_Arguments, args.addr),
            (DosTag.NP_CloseInput, 0),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        child = ProcessStruct(mem, proc_addr)
        # the args are copied into DOS memory and free on exit
        assert child.arguments.aptr != 0
        assert mem.r_cstr(child.arguments.aptr) == "arg1 arg2"
        assert child.flags.val & ProcessFlags.PRF_FREEARGS
        # and pushed into the input stream for ReadArgs()
        assert bytes(in_fh.unch) == b"arg1 arg2"

        wait_for_child(task, exec_proxy, sig_mask, "args_child")

        fm.close(in_fh)
        exec_proxy.FreeSignal(sig)
        tags.free()
        ctx.alloc.free_cstr(args)
        ctx.alloc.free_cstr(name)
        ctx.alloc.free_memory(code)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_args_regs_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        mem = ctx.mem
        fm = ctx.dos_lib.file_mgr

        parent = ProcessStruct(mem, ctx.process.proc.addr)
        exec_base = ctx.exec_lib.exec_lib.addr
        sig = exec_proxy.AllocSignal(-1)
        sig_mask = 1 << sig
        code = ctx.alloc.alloc_memory(64, label="args_code")
        scratch = ctx.alloc.alloc_memory(8, label="args_scratch")
        write_args_child_code(
            mem, code.addr, exec_base, parent.addr, sig_mask, scratch.addr
        )
        name = ctx.alloc.alloc_cstr("args_regs_child")
        args = ctx.alloc.alloc_cstr("arg1 arg2")
        in_fh = fm.open(None, "NIL:", "r")
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_Entry, code.addr),
            (DosTag.NP_Name, name.addr),
            (DosTag.NP_Input, in_fh.b_addr),
            (DosTag.NP_Arguments, args.addr),
            (DosTag.NP_CloseInput, 0),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        child = ProcessStruct(mem, proc_addr)
        arg_addr = child.arguments.aptr
        assert arg_addr != 0
        assert mem.r_cstr(arg_addr) == "arg1 arg2"

        wait_for_child(task, exec_proxy, sig_mask, "args_regs_child")
        # RKRM: the argument string is loaded into A0 and its length into D0
        # before the child's entry point runs
        assert mem.r32(scratch.addr) == len("arg1 arg2")
        assert mem.r32(scratch.addr + 4) == arg_addr

        fm.close(in_fh)
        exec_proxy.FreeSignal(sig)
        tags.free()
        ctx.alloc.free_cstr(args)
        ctx.alloc.free_cstr(name)
        ctx.alloc.free_memory(scratch)
        ctx.alloc.free_memory(code)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_exit_handler_test(vamos_task):
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
        handler = ctx.alloc.alloc_memory(16, label="exit_handler")
        scratch = ctx.alloc.alloc_memory(8, label="exit_scratch")
        write_exit_handler(mem, handler.addr, scratch.addr)
        name = ctx.alloc.alloc_cstr("exit_child")
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_Entry, code.addr),
            (DosTag.NP_Name, name.addr),
            (DosTag.NP_ExitCode, handler.addr),
            (DosTag.NP_ExitData, 0x1234),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        child = ProcessStruct(mem, proc_addr)
        assert child.exit_code.aptr == handler.addr
        assert child.exit_data.val == 0x1234

        wait_for_child(task, exec_proxy, sig_mask, "exit_child")
        # the handler was called with (return code, exit data)
        assert mem.r32(scratch.addr) == 42
        assert mem.r32(scratch.addr + 4) == 0x1234

        exec_proxy.FreeSignal(sig)
        tags.free()
        ctx.alloc.free_memory(scratch)
        ctx.alloc.free_memory(handler)
        ctx.alloc.free_memory(code)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_notify_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        mem = ctx.mem

        code = ctx.alloc.alloc_memory(4, label="child_code")
        write_child_exit_code(mem, code.addr, 42)
        name = ctx.alloc.alloc_cstr("notify_child")
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_Entry, code.addr),
            (DosTag.NP_Name, name.addr),
            (DosTag.NP_NotifyOnDeath, 1),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        child = ProcessStruct(mem, proc_addr)
        assert child.flags.val & ProcessFlags.PRF_NOTIFYONDEATH

        # the child dies and signals us with SIGF_CHILD
        assert exec_proxy.Wait(SIGF_CHILD) == SIGF_CHILD
        assert task.find_task("notify_child") is None

        tags.free()
        ctx.alloc.free_memory(code)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_free_seglist_test(vamos_task):
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
        b_addr = seg_list.get_baddr()
        # register the seglist as a DOS-managed one (like LoadSeg)
        ctx.seg_loader.infos[b_addr] = SegLoadInfo(seg_list)
        ctx.dos_lib.seg_lists[b_addr] = "child_prog"
        name = ctx.alloc.alloc_cstr("free_child")
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_SegList, b_addr),
            (DosTag.NP_Name, name.addr),
            (DosTag.NP_StackSize, 4096),
            (DosTag.NP_FreeSegList, 1),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        child = ProcessStruct(mem, proc_addr)
        assert child.seg_list.bptr == b_addr
        assert child.flags.val & ProcessFlags.PRF_FREESEGLIST

        wait_for_child(task, exec_proxy, sig_mask, "free_child")
        # NP_FreeSegList=TRUE: DOS frees the seglist on exit
        assert b_addr not in ctx.dos_lib.seg_lists
        assert b_addr not in ctx.seg_loader.infos

        exec_proxy.FreeSignal(sig)
        tags.free()
        ctx.alloc.free_cstr(name)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_new_proc_keep_seglist_test(vamos_task):
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
        b_addr = seg_list.get_baddr()
        # register the seglist as a DOS-managed one (like LoadSeg)
        ctx.seg_loader.infos[b_addr] = SegLoadInfo(seg_list)
        ctx.dos_lib.seg_lists[b_addr] = "keep_prog"
        name = ctx.alloc.alloc_cstr("keep_seg_child")
        # no NP_FreeSegList tag: the RKRM default is DOSFALSE
        tags = TagList.alloc(
            ctx.alloc,
            (DosTag.NP_SegList, b_addr),
            (DosTag.NP_Name, name.addr),
            (DosTag.NP_StackSize, 4096),
        )

        proc_addr = dos_proxy.CreateNewProc(tags)
        assert proc_addr != 0
        child = ProcessStruct(mem, proc_addr)
        assert not (child.flags.val & ProcessFlags.PRF_FREESEGLIST)

        wait_for_child(task, exec_proxy, sig_mask, "keep_seg_child")
        # NP_FreeSegList defaults to FALSE: the caller keeps the seglist
        assert b_addr in ctx.dos_lib.seg_lists
        assert b_addr in ctx.seg_loader.infos

        # release the seglist DOS kept alive
        ctx.seg_loader.unload_seglist(b_addr)
        del ctx.dos_lib.seg_lists[b_addr]
        exec_proxy.FreeSignal(sig)
        tags.free()
        ctx.alloc.free_cstr(name)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_create_proc_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        mem = ctx.mem

        parent = ProcessStruct(mem, ctx.process.proc.addr)
        # RKRM: CreateProc copies the caller's pr_WindowPtr unconditionally
        parent.window_ptr.aptr = 0x1234
        exec_base = ctx.exec_lib.exec_lib.addr
        sig = exec_proxy.AllocSignal(-1)
        sig_mask = 1 << sig
        seg_list = SegList.alloc(ctx.alloc, [CHILD_CODE_SIZE])
        write_child_code(mem, seg_list.get_start_pc(), exec_base, parent.addr, sig_mask)
        b_addr = seg_list.get_baddr()
        # register the seglist as a DOS-managed one (like LoadSeg)
        ctx.seg_loader.infos[b_addr] = SegLoadInfo(seg_list)
        ctx.dos_lib.seg_lists[b_addr] = "legacy_prog"
        name = ctx.alloc.alloc_cstr("legacy_proc")

        # CreateProc returns the pr_MsgPort, not the Process struct
        msg_port_addr = dos_proxy.CreateProc(name.addr, 5, b_addr, 4096)
        assert msg_port_addr != 0
        child_task = task.find_task("legacy_proc")
        assert child_task is not None
        child = child_task.map_task.get_ami_process()
        assert child.msg_port.addr == msg_port_addr
        assert child.task.node.pri.val == 5
        assert child.window_ptr.aptr == 0x1234
        # AOS 3.x compat: no input/output handles and they are not closed
        assert child.cis.bptr == 0
        assert child.cos.bptr == 0
        assert not (child.flags.val & ProcessFlags.PRF_CLOSEINPUT)
        assert not (child.flags.val & ProcessFlags.PRF_CLOSEOUTPUT)
        assert not (child.flags.val & ProcessFlags.PRF_FREESEGLIST)

        wait_for_child(task, exec_proxy, sig_mask, "legacy_proc")
        # the caller's seglist is kept (NP_FreeSegList=FALSE)
        assert b_addr in ctx.dos_lib.seg_lists
        assert b_addr in ctx.seg_loader.infos
        parent.window_ptr.aptr = 0

        # release the seglist DOS kept alive
        ctx.seg_loader.unload_seglist(b_addr)
        del ctx.dos_lib.seg_lists[b_addr]
        exec_proxy.FreeSignal(sig)
        ctx.alloc.free_cstr(name)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


# ----- SystemTagList/Execute redirection (Step 3) -----


def write_redir_child_code(mem, pc, dos_base, buf_addr):
    """child code: copy one byte from Input() to Output(), then return 0"""
    code = bytearray()

    def op16(val):
        code.extend((val & 0xFFFF).to_bytes(2, "big"))

    def op32(val):
        code.extend((val & 0xFFFFFFFF).to_bytes(4, "big"))

    op16(0x2C7C)
    op32(dos_base)  # movea.l #dos_base,a6
    op16(0x4EAE)
    op16(LVO_INPUT)  # jsr Input(a6)   -> d0 = input fh
    op16(0x2A00)  # move.l d0,d5
    op16(0x4EAE)
    op16(LVO_OUTPUT)  # jsr Output(a6)  -> d0 = output fh
    op16(0x2C00)  # move.l d0,d6
    op16(0x2205)  # move.l d5,d1
    op16(0x243C)
    op32(buf_addr)  # move.l #buf,d2
    op16(0x7601)  # moveq #1,d3
    op16(0x4EAE)
    op16(LVO_READ)  # jsr Read(a6)    -> d0 = bytes read
    op16(0x2600)  # move.l d0,d3
    op16(0x2206)  # move.l d6,d1
    op16(0x243C)
    op32(buf_addr)  # move.l #buf,d2
    op16(0x4EAE)
    op16(LVO_WRITE)  # jsr Write(a6)
    op16(0x7000)  # moveq #0,d0
    op16(0x4E75)  # rts
    mem.w_block(pc, bytes(code))


def _install_redir_command(ctx):
    """register an in-memory ``redircmd`` and make the current process a
    non-shell command runner, so SystemTagList() takes the non-native path.

    Returns the scratch buffer used by the child code.
    """
    dos_base = ctx.dos_lib.lib_struct.addr
    buf = ctx.alloc.alloc_memory(4, label="redir_buf")
    seg_list = SegList.alloc(ctx.alloc, [REDIR_CODE_SIZE])
    write_redir_child_code(ctx.mem, seg_list.get_start_pc(), dos_base, buf.addr)
    b_addr = seg_list.get_baddr()
    # register the seglist so Process.load_binary finds it under any path
    ctx.seg_loader.infos[b_addr] = SegLoadInfo(seg_list, name="redircmd")
    ctx.seg_loader.load_ami_seglist = lambda path, lock=None, file_opener=None: b_addr
    # the current process runs a command, not a shell (non-native path)
    cwd_lock = ctx.dos_lib.lock_mgr.create_lock(None, "root:", False)
    ctx.process.is_native_shell = lambda: False
    ctx.process.cwd_lock = cwd_lock
    ctx.process.cwd = "root:"
    return buf


def pytask_dos_system_tag_list_redir_test(vamos_task):
    """SystemTagList() honours '<' and '>' on the command line"""

    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        fm = ctx.dos_lib.file_mgr
        alloc = ctx.alloc
        buf = _install_redir_command(ctx)

        # input file holding a single byte
        in_fh = fm.open(None, "ram:redir_in.txt", "w")
        assert in_fh is not None
        in_fh.write(b"Z")
        fm.close(in_fh)

        cmd = alloc.alloc_cstr("redircmd <ram:redir_in.txt >ram:redir_out.txt")
        assert dos_proxy.SystemTagList(cmd.addr, None) == 0
        alloc.free_cstr(cmd)

        # the child copied the byte from the redirected input to the output
        out_fh = fm.open(None, "ram:redir_out.txt", "r")
        assert out_fh is not None
        assert out_fh.read(16) == b"Z"
        fm.close(out_fh)

        alloc.free_memory(buf)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_execute_redir_test(vamos_task):
    """Execute() forwards its input/output handles to the command"""

    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        fm = ctx.dos_lib.file_mgr
        alloc = ctx.alloc
        buf = _install_redir_command(ctx)

        in_fh = fm.open(None, "ram:exec_in.txt", "w")
        in_fh.write(b"Q")
        fm.close(in_fh)
        in_fh = fm.open(None, "ram:exec_in.txt", "r")
        out_fh = fm.open(None, "ram:exec_out.txt", "w")

        cmd = alloc.alloc_cstr("redircmd")
        assert dos_proxy.Execute(cmd.addr, in_fh.b_addr, out_fh.b_addr) == DOSTRUE
        alloc.free_cstr(cmd)
        fm.close(in_fh)
        fm.close(out_fh)

        out_fh = fm.open(None, "ram:exec_out.txt", "r")
        assert out_fh.read(16) == b"Q"
        fm.close(out_fh)

        alloc.free_memory(buf)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]
