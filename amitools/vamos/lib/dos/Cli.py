"""dos.library process and CLI functions (RKRM AmigaDOS 3, "Process
Properties Accessor Functions" and "Creating and Terminating Processes").

Vamos gives every DOS process a CLI structure, so these accessors always
operate on a real shell context. ``CreateProc`` is a thin tag-list wrapper
around ``CreateNewProc`` and ``Exit`` ends the current m68k run through the
machine's normal exit trap. ``Execute`` reuses the ``SystemTagList`` command
runner.
"""

from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.error import VamosInternalError
from amitools.vamos.libstructs import (
    CLIStruct,
    MsgPortFlags,
    ProcessFlags,
    ProcessStruct,
    TaskState,
)
from amitools.vamos.libtypes import DosPacket, DosTag, TagList
from amitools.vamos.log import log_dos
from amitools.vamos.machine import Code
from amitools.vamos.machine.regs import (
    REG_A0,
    REG_A2,
    REG_A5,
    REG_A6,
    REG_D0,
    REG_D1,
    REG_D2,
)
from amitools.vamos.schedule import SchedulerEvent

from .CommandLine import CommandLine
from .Error import (
    DOSFALSE,
    DOSTRUE,
    DOSTRUE_S,
    ERROR_LINE_TOO_LONG,
    ERROR_NOT_IMPLEMENTED,
    ERROR_OBJECT_WRONG_TYPE,
)
from .Process import Process
from .run import run_command as ami_run_command
from .run import run_sub_process
from .Var import copy_local_vars, free_local_vars

# the AmigaDOS V36 process table size returned by MaxCli()
MAX_CLI = 256

# the exec signal a dying child sends its parent (NP_NotifyOnDeath)
SIGF_CHILD = 1 << 1

# the exec signal a synchronous child sends its waiting parent (NP_Synchronous).
# SIGB_SINGLE is a reserved per-task signal bit (Task.new_task marks 0..15 as
# allocated), so AllocSignal() never hands it out to the guest.
SIGF_SINGLE = 1 << 4


def _ami_proc(ctx):
    process = ctx.process
    if process is None:
        return None
    get_proc = getattr(process, "get_ami_process", None)
    if get_proc is not None:
        return get_proc()
    return getattr(process, "this_task", None)


def _cli(ctx):
    process = ctx.process
    if process is None:
        return None
    cli_addr = process.get_cli_struct()
    if cli_addr == 0:
        return None
    return CLIStruct(ctx.mem, cli_addr)


def _copy_out(ctx, buf, max_len, text):
    """copy text as C string, return the resulting IoErr code"""
    text = text or ""
    if max_len <= 0:
        return ERROR_LINE_TOO_LONG if text else 0
    if len(text) >= max_len:
        ctx.mem.w_cstr(buf, text[: max_len - 1])
        return ERROR_LINE_TOO_LONG
    ctx.mem.w_cstr(buf, text)
    return 0


# ----- process creation/termination -----


def create_proc(dos, ctx, name, pri, seglist, stack_size):
    """CreateProc(): legacy NP_SegList based process creation"""
    if seglist == 0:
        log_dos.warning("CreateProc: no seglist")
        return 0
    # RKRM: CreateProc() copies pr_ConsoleTask and pr_WindowPtr from the caller
    # unconditionally (NULL/0 for a task), unlike CreateNewProc's NP_WindowPtr
    # default rule. pr_WindowPtr must therefore be passed explicitly.
    parent_addr = _current_proc_addr(ctx)
    parent = ProcessStruct(ctx.mem, parent_addr) if parent_addr else None
    window_ptr = parent.window_ptr.aptr if parent else 0
    tags = [
        (DosTag.NP_SegList, seglist & 0xFFFFFFFF),
        (DosTag.NP_StackSize, stack_size & 0xFFFFFFFF),
        (DosTag.NP_Priority, pri & 0xFFFFFFFF),
        (DosTag.NP_WindowPtr, window_ptr),
        # AOS 3.x compat (AROS createproc.c): CreateProc must not free the
        # caller's seglist, must not close the inherited handles and must not
        # break Forbid() locking, so it passes 0 for the dirs/handles.
        (DosTag.NP_FreeSegList, 0),
        (DosTag.NP_CurrentDir, 0),
        (DosTag.NP_HomeDir, 0),
        (DosTag.NP_Input, 0),
        (DosTag.NP_Output, 0),
        (DosTag.NP_CloseInput, 0),
        (DosTag.NP_CloseOutput, 0),
    ]
    name_mem = None
    if name:
        name_mem = ctx.alloc.alloc_cstr(name, label="CreateProcName")
        tags.append((DosTag.NP_Name, name_mem.addr))
    tag_list = TagList.alloc(ctx.alloc, *tags)
    try:
        proc_addr = dos.CreateNewProc(ctx, tag_list)
    finally:
        tag_list.free()
        if name_mem is not None:
            ctx.alloc.free_cstr(name_mem)
    if proc_addr == 0:
        log_dos.info("CreateProc(%s, pri=%d) -> failed", name, pri)
        return 0
    # CreateProc() returns the process's pr_MsgPort, not the Process struct
    msg_port_addr = ProcessStruct(ctx.mem, proc_addr).msg_port.addr
    log_dos.info(
        "CreateProc(%s, pri=%d) -> msg_port=%06x (proc=%06x)",
        name,
        pri,
        msg_port_addr,
        proc_addr,
    )
    return msg_port_addr


# sentinel to tell "tag not given" apart from an explicit zero value
_UNSET = object()


def _tag_data(tags, tag):
    """tag value or ``None`` when the tag is absent (an explicit 0 is kept)"""
    val = tags.get_tag_data(tag, _UNSET)
    return None if val is _UNSET else val


def _current_proc_addr(ctx):
    """address of the DOS process currently running (0 if none)"""
    # exec's ThisTask variable is the canonical current process
    exec_lib = getattr(ctx, "exec_lib", None)
    if exec_lib is not None:
        el = getattr(exec_lib, "exec_lib", None)
        if el is not None:
            addr = el.this_task.aptr
            if addr:
                return addr
    process = getattr(ctx, "process", None)
    if process is not None:
        proc = getattr(process, "proc", None)
        if proc is not None:
            return proc.addr
        task = getattr(process, "this_task", None)
        if task is not None:
            return task.addr
    return 0


def _new_proc_tags(ctx, tags):
    """read the ``NP_*`` tag list into a parameter set (``None`` on error)"""
    tag_list = tags.to_list(map_enum=DosTag, do_map=True)
    log_dos.info("CreateNewProc: tags=%s", tag_list)

    entry_pc = _tag_data(tags, DosTag.NP_Entry)
    seglist_bptr = _tag_data(tags, DosTag.NP_SegList)
    stack_size = _tag_data(tags, DosTag.NP_StackSize)
    name_ptr = _tag_data(tags, DosTag.NP_Name)
    priority = _tag_data(tags, DosTag.NP_Priority)
    current_dir = _tag_data(tags, DosTag.NP_CurrentDir)
    home_dir = _tag_data(tags, DosTag.NP_HomeDir)
    input_fh = _tag_data(tags, DosTag.NP_Input)
    output_fh = _tag_data(tags, DosTag.NP_Output)
    error_fh = _tag_data(tags, DosTag.NP_Error)
    close_input = _tag_data(tags, DosTag.NP_CloseInput)
    close_output = _tag_data(tags, DosTag.NP_CloseOutput)
    close_error = _tag_data(tags, DosTag.NP_CloseError)
    console_task = _tag_data(tags, DosTag.NP_ConsoleTask)
    window_ptr = _tag_data(tags, DosTag.NP_WindowPtr)
    arguments_ptr = _tag_data(tags, DosTag.NP_Arguments)
    notify_on_death = _tag_data(tags, DosTag.NP_NotifyOnDeath)
    exit_code = _tag_data(tags, DosTag.NP_ExitCode)
    exit_data = _tag_data(tags, DosTag.NP_ExitData)
    free_seglist = _tag_data(tags, DosTag.NP_FreeSegList)
    user_data = _tag_data(tags, DosTag.NP_UserData)
    copy_vars = _tag_data(tags, DosTag.NP_CopyVars)
    synchronous = _tag_data(tags, DosTag.NP_Synchronous)

    # tags that vamos accepts but does not act on yet
    if _tag_data(tags, DosTag.NP_Cli):
        log_dos.warning("CreateNewProc: NP_Cli is not supported (ignored)")
    if _tag_data(tags, DosTag.NP_Path):
        log_dos.warning("CreateNewProc: NP_Path is not supported (ignored)")
    if _tag_data(tags, DosTag.NP_CommandName):
        log_dos.warning("CreateNewProc: NP_CommandName is not supported (ignored)")

    if entry_pc is None and seglist_bptr is None:
        log_dos.warning("CreateNewProc: no NP_Entry or NP_SegList")
        return None
    if entry_pc is None:
        entry_pc = (seglist_bptr << 2) + 4

    parent_addr = _current_proc_addr(ctx)
    parent = ProcessStruct(ctx.mem, parent_addr) if parent_addr else None

    # RKRM AmigaDOS defaults: name "New Process", stack 4000, priority 0;
    # input/output default to NIL: (see _spawn) and the error stream to ZERO.
    # Current/home dir are resolved in _spawn (they need the lock manager to
    # DupLock the caller's locks); the console task is inherited here.
    if stack_size is None:
        stack_size = 4000
    if name_ptr:
        name = ctx.mem.r_cstr(name_ptr)
    else:
        name = "New Process"
    if priority is None:
        priority = 0
    if console_task is None:
        console_task = parent.console_task.aptr if parent else 0
    if window_ptr is None:
        # RKRM: copy the caller's window pointer only if it is NULL or -1,
        # otherwise use NULL; a task (no parent) gets NULL
        if parent is None:
            window_ptr = 0
        else:
            parent_window = parent.window_ptr.aptr
            window_ptr = parent_window if parent_window in (0, 0xFFFFFFFF) else 0
    if user_data is None:
        user_data = 0
    # NP_CopyVars defaults to TRUE: the child gets a deep copy of the caller's
    # local shell variables and aliases (RKRM "Creating and Terminating
    # Processes"). An explicit 0 leaves the child with no variables.
    if copy_vars is None:
        copy_vars = 1

    # input/output are closed on exit by default; the error stream is *not*
    # (RKRM and the NDK dos/dostags.h agree on this asymmetric default)
    if close_input is None:
        close_input = 1
    if close_output is None:
        close_output = 1
    if close_error is None:
        close_error = 0

    # NP_Arguments is copied into DOS memory and pushed into the input
    # buffer so that ReadArgs() works in the child
    arguments = None
    if arguments_ptr is not None:
        arguments = ctx.mem.r_cstr(arguments_ptr) if arguments_ptr else ""

    flags = 0
    if close_input:
        flags |= ProcessFlags.PRF_CLOSEINPUT
    if close_output:
        flags |= ProcessFlags.PRF_CLOSEOUTPUT
    if close_error:
        flags |= ProcessFlags.PRF_CLOSEERROR
    if free_seglist:
        flags |= ProcessFlags.PRF_FREESEGLIST
    if notify_on_death:
        flags |= ProcessFlags.PRF_NOTIFYONDEATH
    if synchronous:
        flags |= ProcessFlags.PRF_SYNCHRONOUS
    if arguments is not None:
        flags |= ProcessFlags.PRF_FREEARGS

    log_dos.info(
        "CreateNewProc: name=%s entry=%06x stack=%d pri=%d flags=%x",
        name,
        entry_pc,
        stack_size,
        priority,
        int(flags),
    )
    return {
        "name": name,
        "entry_pc": entry_pc,
        "seglist_bptr": seglist_bptr if seglist_bptr is not None else 0,
        "stack_size": stack_size,
        "priority": priority,
        "current_dir": current_dir,
        "home_dir": home_dir,
        "input_fh": input_fh,
        "output_fh": output_fh,
        "error_fh": error_fh,
        "console_task": console_task,
        "window_ptr": window_ptr,
        "user_data": user_data,
        "arguments": arguments,
        "flags": flags,
        "exit_code": exit_code or 0,
        "exit_data": exit_data or 0,
        "notify_on_death": 1 if notify_on_death else 0,
        "parent_addr": parent_addr,
        "copy_vars": bool(copy_vars),
        "synchronous": bool(synchronous),
    }


def _open_nil_fh(dos, mode, label):
    """open the ``NIL:`` handle a missing NP_Input/NP_Output needs"""
    fh = dos.file_mgr.open(None, "NIL:", mode)
    if fh is None:
        log_dos.warning("CreateNewProc: cannot open NIL: for %s", label)
    return fh


def _resolve_child_fh(dos, bptr, mode, label):
    """the caller's handle, or the NIL: default when the tag was absent

    An explicit ``0`` (BNULL) is kept: it means "no handle", not "NIL:"
    (AROS only opens NIL: for a tag that was not specified at all).
    """
    if bptr is not None:
        return bptr
    fh = _open_nil_fh(dos, mode, label)
    return fh.b_addr if fh is not None else 0


def _resolve_child_dir(dos, explicit_bptr, parent_bptr, label):
    """the child's current/home dir lock BPTR (RKRM ``NP_CurrentDir``)

    An explicit tag lock is absorbed by the child; an absent tag duplicates
    the caller's lock (``ZERO`` for a task). Returns ``(bptr, owned)`` where
    ``owned`` marks a lock obtained here that ``_spawn()`` must release if
    creating the process fails.
    """
    if explicit_bptr is not None:
        return explicit_bptr, explicit_bptr != 0
    if not parent_bptr:
        return 0, False
    parent_lock = dos.lock_mgr.get_by_b_addr(parent_bptr)
    if parent_lock is None:
        return 0, False
    dup = dos.lock_mgr.dup_lock(parent_lock)
    if dup is None:
        log_dos.warning(
            "CreateNewProc: cannot duplicate parent %s lock %06x", label, parent_bptr
        )
        return 0, False
    return dup.b_addr, True


def _release_lock_bptr(dos, bptr):
    """release a DOS lock by BPTR, ignoring an already-freed lock"""
    if not bptr:
        return
    try:
        lock = dos.lock_mgr.get_by_b_addr(bptr)
    except (VamosInternalError, IndexError, AttributeError, TypeError):
        lock = None
    if lock is not None:
        dos.lock_mgr.release_lock(lock)


def _spawn(dos, ctx, p):
    """create and schedule the child process described by ``p``"""
    # NP_Arguments is copied into DOS memory *before* the child starts so its
    # entry point receives the string in A0 and its length in D0, as documented
    # in RKRM ("the string and its lengths will be loaded into registers A0 and
    # D0 before execution of the process begins").
    arg_mem = None
    arg_addr = 0
    arg_len = 0
    if p["arguments"] is not None:
        arg_mem = ctx.alloc.alloc_cstr(p["arguments"], label="CreateNewProc_Args")
        arg_addr = arg_mem.addr
        arg_len = len(p["arguments"])

    odg_base = getattr(ctx, "odg_base", 0)
    start_regs = {
        REG_D0: arg_len,
        REG_A0: arg_addr,
        # D2 holds the stack size and the old DOS register guard is installed in
        # A2/A5/A6, exactly like a process vamos loaded from a seglist
        REG_D2: p["stack_size"],
        REG_A2: odg_base,
        REG_A5: odg_base,
        REG_A6: odg_base,
    }
    # the child is a process of its own: the scheduler runs it beside
    # its parent, and it is freed once its task ends (child_proc_event)
    # RKRM NP_CurrentDir/NP_HomeDir: an explicit tag lock is absorbed by the
    # child; an absent tag duplicates the caller's lock. Both are released on
    # process exit (the current dir only when non-ZERO -> PRF_FREECURRDIR).
    parent_addr = p["parent_addr"]
    parent = ProcessStruct(ctx.mem, parent_addr) if parent_addr else None
    parent_current = parent.current_dir.bptr if parent else 0
    parent_home = parent.home_dir.bptr if parent else 0
    current_dir, current_owned = _resolve_child_dir(
        dos, p["current_dir"], parent_current, "current dir"
    )
    home_dir, home_owned = _resolve_child_dir(
        dos, p["home_dir"], parent_home, "home dir"
    )
    flags = int(p["flags"])
    if current_dir:
        flags |= ProcessFlags.PRF_FREECURRDIR
    try:
        child = dos.create_child_process(
            ctx,
            p["name"],
            stack_size=p["stack_size"],
            start_pc=p["entry_pc"],
            start_regs=start_regs,
        )
    except Exception:
        # creating the process failed: the copied arguments are not owned by
        # anybody yet and have to be released (RKRM "What's Released on Error?"),
        # and so are the locks obtained/absorbed for the new process
        if arg_mem is not None:
            ctx.alloc.free_cstr(arg_mem)
        if current_owned:
            _release_lock_bptr(dos, current_dir)
        if home_owned:
            _release_lock_bptr(dos, home_dir)
        raise
    proc = child.proc
    task = proc.task
    stack = child.get_stack()
    task.node.pri.val = p["priority"]
    task.sp_reg.aptr = stack.get_initial_sp()
    task.sp_lower.aptr = stack.get_lower()
    task.sp_upper.aptr = stack.get_upper()
    task.tc_UserData.aptr = p["user_data"]
    proc.stack_size.val = stack.get_size()
    proc.stack_base.bptr = stack.get_lower() >> 2
    proc.seg_list.bptr = p["seglist_bptr"]
    proc.glob_vec.aptr = 0xFFFFFFFF
    proc.current_dir.bptr = current_dir
    proc.home_dir.bptr = home_dir
    proc.window_ptr.aptr = p["window_ptr"]
    proc.console_task.aptr = p["console_task"]
    proc.flags.val = flags
    proc.exit_code.aptr = p["exit_code"]
    proc.exit_data.val = p["exit_data"]

    # NP_Input/NP_Output default to a fresh NIL: open; NP_Error defaults to
    # ZERO (RKRM). An explicit 0 (BNULL) is kept as 0 for all three.
    input_fh = _resolve_child_fh(dos, p["input_fh"], "r", "input")
    output_fh = _resolve_child_fh(dos, p["output_fh"], "w", "output")
    error_fh = p["error_fh"] if p["error_fh"] is not None else 0
    proc.cis.bptr = input_fh
    proc.cos.bptr = output_fh
    proc.ces.bptr = error_fh

    # NP_CopyVars: every child gets its own local-variable table so that it has
    # an independent set from the caller; the tag (default TRUE) then decides
    # whether the caller's shell variables and aliases are deep-copied into it
    # (RKRM). The table is released when the child terminates.
    child._local_vars = {}
    if p["copy_vars"]:
        copy_local_vars(dos, ctx, child)

    # remember what the exit cleanup in child_proc_event() needs
    child.dos_ctx = ctx
    child.dos_flags = flags
    child.dos_exit_code = p["exit_code"]
    child.dos_exit_data = p["exit_data"]
    child.dos_notify = p["notify_on_death"]
    child.dos_parent_addr = p["parent_addr"]
    # the caller's scheduler task, used to wake it for NP_Synchronous. This is
    # also available for a task caller, where there is no process address.
    child.dos_parent_task = (
        ctx.scheduler.get_running_task() if ctx.scheduler is not None else None
    )
    child.dos_arg_mem = arg_mem

    # NP_Arguments: record it and push it into the input buffer so that
    # ReadArgs() sees it in the child (RKRM)
    if arg_mem is not None:
        proc.arguments.aptr = arg_addr
        fh = dos.file_mgr.get_by_b_addr(input_fh)
        if fh is not None:
            fh.setbuf(p["arguments"])

    # the process port is signalled with SIGB_DOS. it is no public port:
    # FindPort() does not find it, a child that wants one adds its own
    port = proc.msg_port
    port.new(flags=MsgPortFlags.PA_SIGNAL, sig_bit=8, sig_task=task)
    port_addr = port.addr
    if not ctx.exec_lib.port_mgr.has_port(port_addr):
        ctx.exec_lib.port_mgr.register_port(port_addr)

    sched_task = child.get_sched_task()
    dos.child_procs[sched_task] = child
    ctx.scheduler.add_task(sched_task)
    # add_task() marks the task TS_ADDED. a new process is ready on the Amiga
    task.state.val = TaskState.TS_READY

    log_dos.info(
        "CreateNewProc: created process %06x entry=%06x port=%06x flags=%x",
        proc.addr,
        p["entry_pc"],
        port_addr,
        flags,
    )

    # NP_Synchronous: the caller blocks until the child has terminated. AROS
    # implements this by setting PRF_WAITINGFORCHILD on the parent and waiting
    # on SIGF_SINGLE, which the child's exit path signals. (The RKRM book notes
    # the tag is ignored by AmigaDOS 3; vamos follows AROS/later AmigaDOS and
    # implements it as a superset, like NP_NotifyOnDeath.)
    if p["synchronous"]:
        _wait_for_sync_child(ctx, sched_task, child.dos_parent_task, parent_addr)

    return proc.addr


def create_new_proc(dos, ctx, tags):
    """CreateNewProc(): spawn a process from an ``NP_*`` tag list"""
    if tags is None:
        log_dos.warning("CreateNewProc: NULL tags")
        return 0
    params = _new_proc_tags(ctx, tags)
    if params is None:
        return 0
    return _spawn(dos, ctx, params)


# ----- child process shutdown -----


def _close_child_fh(dos, bptr, label):
    """close one of the child's handles if it is safe to do so"""
    if not bptr:
        return
    try:
        fh = dos.file_mgr.get_by_b_addr(bptr)
    except (ValueError, VamosInternalError):
        fh = None
    if fh is None:
        return
    # never close the shared standard handles: they are not ours
    if fh in (dos.file_mgr.std_input, dos.file_mgr.std_output):
        log_dos.warning("CreateNewProc: not closing shared std %s handle", label)
        return
    log_dos.info("CreateNewProc: closing child %s handle", label)
    dos.file_mgr.close(fh)


def _free_child_seglist(dos, ctx, bptr):
    """unload the child's seglist if DOS manages it (NP_FreeSegList)"""
    if not bptr:
        return
    if bptr >= 0x80000000:
        bptr -= 0x100000000
    if bptr in dos.seg_lists:
        dos._unload_seg_list(ctx, bptr)
        return
    seg_loader = getattr(ctx, "seg_loader", None)
    if seg_loader is not None and bptr in getattr(seg_loader, "infos", {}):
        seg_loader.unload_seglist(abs(bptr))
        return
    log_dos.info(
        "CreateNewProc: NP_FreeSegList set but seglist %06x is not managed by DOS",
        bptr,
    )


def _call_exit_handler(dos, ctx, child, ret_code, exit_code, exit_data):
    """call the NP_ExitCode handler with the process return code"""
    runner = getattr(ctx, "runner", None)
    if runner is None:
        log_dos.warning("CreateNewProc: no runner to call NP_ExitCode %06x", exit_code)
        return
    code = Code(
        pc=exit_code,
        sp=child.get_stack().get_initial_sp(),
        set_regs={
            REG_D0: ret_code & 0xFFFFFFFF,
            REG_D1: exit_data & 0xFFFFFFFF,
        },
        get_regs=[],
    )
    log_dos.info(
        "CreateNewProc: calling NP_ExitCode %06x(rc=%d, data=%d)",
        exit_code,
        ret_code,
        exit_data,
    )
    try:
        run_state = runner(code)
    except Exception as e:  # the exit handler must not break the shutdown
        log_dos.warning("CreateNewProc: NP_ExitCode %06x failed: %s", exit_code, e)
        return
    if run_state is not None and run_state.mach_error is not None:
        log_dos.warning(
            "CreateNewProc: NP_ExitCode %06x machine error: %s",
            exit_code,
            run_state.mach_error,
        )


def _find_parent_task(ctx, parent_addr):
    """the scheduler task that owns the Amiga task/process at ``parent_addr``"""
    scheduler = getattr(ctx, "scheduler", None)
    if scheduler is None or parent_addr == 0:
        return None

    def pred(task):
        map_task = getattr(task, "map_task", None)
        if map_task is None:
            return False
        ami = map_task.get_ami_task()
        return ami is not None and ami.addr == parent_addr

    return scheduler.find_task_pred_func(pred)


def _notify_parent_sync(ctx, parent_task, parent_addr):
    """wake a parent blocked in a synchronous CreateNewProc (NP_Synchronous)"""
    if parent_task is None:
        parent_task = _find_parent_task(ctx, parent_addr)
    if parent_task is None:
        log_dos.warning(
            "CreateNewProc: NP_Synchronous parent %06x not found", parent_addr
        )
        return
    # clear the PRF_WAITINGFORCHILD the caller set while it waits (AROS)
    if parent_addr:
        proc = ProcessStruct(ctx.mem, parent_addr)
        proc.flags.val &= ~ProcessFlags.PRF_WAITINGFORCHILD
    log_dos.info("CreateNewProc: signalling parent %06x (SIGF_SINGLE)", parent_addr)
    parent_task.set_signal(SIGF_SINGLE, SIGF_SINGLE)


def _notify_parent_death(ctx, parent_task, parent_addr):
    """signal the parent task that a child died (NP_NotifyOnDeath)"""
    if parent_task is None:
        parent_task = _find_parent_task(ctx, parent_addr)
    if parent_task is None:
        log_dos.warning(
            "CreateNewProc: NP_NotifyOnDeath parent %06x not found", parent_addr
        )
        return
    log_dos.info("CreateNewProc: signalling parent %06x (SIGF_CHILD)", parent_addr)
    parent_task.set_signal(SIGF_CHILD, SIGF_CHILD)


def _notify_parent(ctx, parent_task, parent_addr, flags):
    """deliver a dying child's completion signals to its parent"""
    # the parent may itself have terminated (its process memory is freed then)
    if parent_task is not None and parent_task.get_state() == TaskState.TS_REMOVED:
        return
    # NP_Synchronous must be signalled first in case both tags are set (AROS)
    if flags & ProcessFlags.PRF_SYNCHRONOUS:
        _notify_parent_sync(ctx, parent_task, parent_addr)
    if flags & ProcessFlags.PRF_NOTIFYONDEATH:
        _notify_parent_death(ctx, parent_task, parent_addr)


def _schedule_child_notify(ctx, parent_task, parent_addr, flags):
    """deliver the completion signals once the dying child's greenlet has ended

    Signalling from inside the child's greenlet would switch back to the
    scheduler before child.free() and leave the greenlet suspended forever,
    leaking the process. The scheduler runs this callback on its own greenlet
    after the child has fully unwound, so the child is freed first.
    """
    scheduler = getattr(ctx, "scheduler", None)
    if scheduler is None or not scheduler.running:
        _notify_parent(ctx, parent_task, parent_addr, flags)
        return

    def deliver():
        scheduler.remove_after_schedule_callback(deliver)
        _notify_parent(ctx, parent_task, parent_addr, flags)

    scheduler.add_after_schedule_callback(deliver)


def _wait_for_sync_child(ctx, child_task, parent_task, parent_addr):
    """block the caller until a synchronous child task has terminated"""
    if parent_task is None:
        # no task is running (e.g. driven from Python): cannot block
        log_dos.warning("CreateNewProc: NP_Synchronous without a running task")
        return
    # mark the parent as waiting (AROS PRF_WAITINGFORCHILD) and clear a stale
    # completion signal before sleeping; the child cannot run until we yield
    if parent_addr:
        proc = ProcessStruct(ctx.mem, parent_addr)
        proc.flags.val |= ProcessFlags.PRF_WAITINGFORCHILD
    parent_task.set_signal(0, SIGF_SINGLE)
    log_dos.info("CreateNewProc: NP_Synchronous waiting for %s", child_task.name)
    parent_task.wait(SIGF_SINGLE)


def _child_exit_cleanup(dos, child, ret_code):
    """emulate the DOS part of a process shutdown before it is freed"""
    ctx = getattr(child, "dos_ctx", None)
    if ctx is None:
        return
    flags = getattr(child, "dos_flags", 0)
    proc = child.proc
    # NP_ExitCode(return code, exit data)
    exit_code = getattr(child, "dos_exit_code", 0)
    if exit_code:
        _call_exit_handler(
            dos, ctx, child, ret_code, exit_code, getattr(child, "dos_exit_data", 0)
        )
    # close the process's handles
    if flags & ProcessFlags.PRF_CLOSEINPUT:
        _close_child_fh(dos, proc.cis.bptr, "input")
    if flags & ProcessFlags.PRF_CLOSEOUTPUT:
        _close_child_fh(dos, proc.cos.bptr, "output")
    if flags & ProcessFlags.PRF_CLOSEERROR:
        _close_child_fh(dos, proc.ces.bptr, "error")
    # unload the seglist
    if flags & ProcessFlags.PRF_FREESEGLIST:
        _free_child_seglist(dos, ctx, proc.seg_list.bptr)
    # release the current directory (PRF_FREECURRDIR) and the home directory
    # (RKRM: pr_HomeDir is always released on process exit when non-ZERO)
    if flags & ProcessFlags.PRF_FREECURRDIR:
        _release_lock_bptr(dos, proc.current_dir.bptr)
    _release_lock_bptr(dos, proc.home_dir.bptr)
    # free the copied NP_Arguments
    arg_mem = getattr(child, "dos_arg_mem", None)
    if arg_mem is not None:
        ctx.alloc.free_cstr(arg_mem)
        child.dos_arg_mem = None
    # NP_CopyVars: release the child's own local shell variables
    free_local_vars(dos, ctx, child)


def child_proc_event(dos, event):
    """free a process made by CreateNewProc() once its task has ended"""
    if event.type != SchedulerEvent.Type.REMOVE_TASK:
        return
    child = dos.child_procs.pop(event.task, None)
    if child is None:
        return
    ret_code = event.task.get_exit_code()
    if ret_code is None:
        # NativeTask only stores exit_code after it has reported REMOVE_TASK,
        # so read the return code the code left in D0 from the run state
        run_state = getattr(event.task, "run_state", None)
        regs = getattr(run_state, "regs", None) if run_state is not None else None
        if regs:
            ret_code = regs[REG_D0] & 0xFF
        else:
            ret_code = 0
    _child_exit_cleanup(dos, child, ret_code)
    port_addr = child.proc.msg_port.addr
    if dos.port_mgr.has_port(port_addr):
        dos.port_mgr.unregister_port(port_addr)
    # remember the completion notifications before the process is freed
    ctx = getattr(child, "dos_ctx", None)
    flags = getattr(child, "dos_flags", 0)
    parent_addr = getattr(child, "dos_parent_addr", 0)
    parent_task = getattr(child, "dos_parent_task", None)
    log_dos.info("CreateNewProc: process %06x ended", child.proc.addr)
    child.free()
    # NP_Synchronous / NP_NotifyOnDeath: wake the parent once this child has
    # fully unwound and been freed
    if ctx is not None and (
        flags & (ProcessFlags.PRF_SYNCHRONOUS | ProcessFlags.PRF_NOTIFYONDEATH)
    ):
        _schedule_child_notify(ctx, parent_task, parent_addr, flags)


def exit_process(dos, ctx, return_code):
    """Exit(): terminate the caller by entering the machine's exit trap"""
    machine = getattr(ctx, "machine", None)
    get_exit = getattr(machine, "get_run_exit_addr", None)
    if get_exit is None:
        log_dos.warning("Exit: no machine exit trap available")
        dos.setioerr(ctx, ERROR_NOT_IMPLEMENTED)
        return return_code
    code = return_code & 0xFFFFFFFF
    ctx.cpu.w_reg(REG_D0, code)
    exit_addr = get_exit()
    ctx.cpu.w_pc(exit_addr)
    log_dos.info("Exit(%d): pc -> %06x", return_code, exit_addr)
    return return_code


# ----- process properties -----


def get_console_task(ctx):
    proc = _ami_proc(ctx)
    if proc is None:
        return 0
    return proc.pr_ConsoleTask.aptr


def set_console_task(ctx, port):
    proc = _ami_proc(ctx)
    if proc is None:
        return 0
    old = proc.pr_ConsoleTask.aptr
    proc.pr_ConsoleTask.aptr = port & 0xFFFFFFFF
    return old


def set_arg_str(ctx, ptr):
    proc = _ami_proc(ctx)
    if proc is None:
        return 0
    old = proc.pr_Arguments.aptr
    proc.pr_Arguments.aptr = ptr & 0xFFFFFFFF
    return old


def get_current_dir(ctx):
    proc = _ami_proc(ctx)
    if proc is None:
        return 0
    return proc.pr_CurrentDir.bptr


def get_program_name(dos, ctx, buf_ptr, max_len):
    prog_name = ctx.process.get_program_name()
    n = len(prog_name)
    # return error if name is too long, but copy buffer size
    if n > max_len - 1:
        dos.setioerr(ctx, ERROR_LINE_TOO_LONG)
        ret = DOSFALSE
        prog_name = prog_name[0:max_len]
    else:
        ret = DOSTRUE
    ctx.mem.w_cstr(buf_ptr, prog_name)
    log_dos.info("GetProgramName() -> '%s' (%d)", prog_name, max_len)
    return ret


def get_program_dir(dos, ctx):
    prog_dir_addr = ctx.process.get_home_dir()
    prog_dir_lock = dos.lock_mgr.get_by_b_addr(prog_dir_addr >> 2)
    log_dos.info("GetProgramDir() -> %s", prog_dir_lock)
    if prog_dir_lock:
        return prog_dir_lock.b_addr
    else:
        return 0


def get_arg_str(dos, ctx):
    arg_ptr = ctx.process.get_arg_str_ptr()
    log_dos.info("GetArgStr() -> %08x", arg_ptr)
    return arg_ptr


def get_current_dir_name(dos, ctx, buf, max_len):
    cli = _cli(ctx)
    if cli is None:
        dos.setioerr(ctx, ERROR_OBJECT_WRONG_TYPE)
        return DOSFALSE
    name = ctx.mem.r_bstr(cli.cli_SetName.aptr)
    # the shell path always reports success, even if it was truncated
    dos.setioerr(ctx, _copy_out(ctx, buf, max_len, name))
    return DOSTRUE


def set_current_dir_name(dos, ctx, str_addr):
    string = ctx.mem.r_cstr(str_addr)[:79]
    cli_addr = dos.Cli(ctx)
    cli = CLIStruct(ctx.mem, cli_addr)
    setaddr = cli.cli_SetName.aptr
    ctx.mem.w_bstr(setaddr, string)
    return DOSTRUE


def set_program_name(dos, ctx, name):
    cli = _cli(ctx)
    if cli is None:
        dos.setioerr(ctx, ERROR_OBJECT_WRONG_TYPE)
        return DOSFALSE
    # cli_CommandName has a fixed 104 byte buffer
    ctx.mem.w_bstr(cli.cli_CommandName.aptr, (name or "")[:103])
    dos.setioerr(ctx, 0)
    return DOSTRUE


def get_prompt(dos, ctx, buf, max_len):
    cli = _cli(ctx)
    if cli is None:
        dos.setioerr(ctx, ERROR_OBJECT_WRONG_TYPE)
        return DOSFALSE
    prompt = ctx.mem.r_bstr(cli.cli_Prompt.aptr)
    dos.setioerr(ctx, _copy_out(ctx, buf, max_len, prompt))
    return DOSTRUE


def set_prompt(dos, ctx, str_addr):
    string = ctx.mem.r_cstr(str_addr)[:59]
    cli_addr = dos.Cli(ctx)
    cli = CLIStruct(ctx.mem, cli_addr)
    setaddr = cli.cli_Prompt.aptr
    ctx.mem.w_bstr(setaddr, string)
    return DOSTRUE


def set_program_dir(ctx, lock_bptr):
    proc = _ami_proc(ctx)
    if proc is None:
        return 0
    old = proc.pr_HomeDir.bptr
    proc.pr_HomeDir.bptr = lock_bptr & 0xFFFFFFFF
    return old


def get_file_sys_task(dos, ctx):
    return ctx.process.this_task.pr_FileSystemTask.aptr


def set_file_sys_task(dos, ctx, port):
    ctx.process.this_task.pr_FileSystemTask.aptr = port


def find_cli_proc(ctx, num):
    # Vamos has no process table with task numbers; report "not found"
    # without touching IoErr (as the AmigaDOS call does)
    log_dos.warning("FindCliProc(%d): no process table in vamos", num)
    return 0


def max_cli(ctx):
    return MAX_CLI


# ----- system/execute -----


def _resolve_redirection(dos, lock, cl, tag_list):
    """resolve the command's input/output handles for ``SystemTagList``

    A redirection on the command line (``<``, ``>``, ``>>``) takes precedence
    over the ``SYS_Input``/``SYS_Output`` handles that ``Execute()`` forwards.
    Returns ``(input_fh, output_fh, owned_fhs)`` or ``None`` when opening a
    redirection file failed; ``owned_fhs`` are the handles opened here that the
    caller has to close once the command has run.
    """
    input_fh = None
    output_fh = None
    owned = []

    redir_in = cl.get_redir_in()
    if redir_in is not None:
        fh = dos.file_mgr.open(lock, redir_in, "r")
        if fh is None:
            log_dos.warning(
                "SystemTagList: cannot open input redirection '%s'", redir_in
            )
            return None
        input_fh = fh
        owned.append(fh)

    redir_out = cl.get_redir_out()
    if redir_out is not None:
        append = cl.is_append_out()
        # '>>' opens read/write (creating the file) and appends at EOF;
        # '>' truncates the file.
        fh = dos.file_mgr.open(lock, redir_out, "rw" if append else "w")
        if fh is None:
            log_dos.warning(
                "SystemTagList: cannot open output redirection '%s'", redir_out
            )
            for o in owned:
                dos.file_mgr.close(o)
            return None
        if append:
            fh.seek(0, 2)
        output_fh = fh
        owned.append(fh)

    # no redirection: fall back to the Execute() SYS_Input/SYS_Output handles
    if input_fh is None and tag_list is not None:
        intag = tag_list.find_tag(DosTag.SYS_Input)
        if intag is not None:
            data = intag.get_data()
            if data:
                input_fh = dos.file_mgr.get_by_b_addr(data)
    if output_fh is None and tag_list is not None:
        outtag = tag_list.find_tag(DosTag.SYS_Output)
        if outtag is not None:
            data = outtag.get_data()
            if data:
                output_fh = dos.file_mgr.get_by_b_addr(data)

    return input_fh, output_fh, owned


def system_tag_list(dos, ctx, cmd, tag_list):
    log_dos.info("SystemTagList: cmd=%s tags=%s ctx=%s", cmd, tag_list, ctx)
    # cmd is at this point a full string of commands to execute.
    # If we're running from the Amiga shell, forward this to the shell
    # anyhow.
    if ctx.process.is_native_shell():
        cli_addr = ctx.process.get_cli_struct()
        cli = CLIStruct(ctx.mem, cli_addr)
        # a caller supplied SYS_Input handle receives the command line, else
        # vamos opens a fresh NIL: stream to push the commands into
        new_input = None
        if tag_list is not None:
            intag = tag_list.find_tag(DosTag.SYS_Input)
            if intag is not None:
                data = intag.get_data()
                if data:
                    new_input = dos.file_mgr.get_by_b_addr(data)
        if new_input is None:
            new_input = dos.file_mgr.open(None, "NIL:", "r")
        if new_input is None:
            log_dos.warning(
                "SystemTagList: can't create new input file handle for "
                "SystemTagList('%s')",
                cmd,
            )
            return 0xFFFFFFFF
        # Push-back the commands into the input buffer.
        if cmd:
            new_input.setbuf(cmd)
        new_stdin = dos.file_mgr.open(None, "*", "rw")
        outtag = tag_list.find_tag(DosTag.SYS_Output) if tag_list is not None else None
        # print "setting new input to %s" % new_input
        # and install this as current input. The shell will read from that
        # instead until it hits the EOF
        input_fhsi = cli.cli_StandardInput.aptr
        input_fhci = cli.cli_CurrentInput.aptr
        if outtag:
            data = outtag.get_data()
            if data != 0:
                output_fhci = cli.cli_StandardOutput.aptr
                cli.cli_StandardOutput.aptr = data << 2
        else:
            output_fhci = None
        cli.cli_CurrentInput.aptr = new_input.mem.addr
        cli.cli_StandardInput.aptr = new_stdin.mem.addr
        cli.cli_Background.val = DOSTRUE_S
        # Create the Packet for the background process.
        packet = ctx.process.run_system()
        stack_size = cli.cli_DefaultStack.val << 2
        current_dir = ctx.process.get_current_dir()
        dup_lock = dos.lock_mgr.dup_lock(dos.get_current_dir(ctx))
        cur_module = cli.cli_Module.aptr
        cur_out = ctx.process.this_task.pr_COS.aptr
        cur_setname = ctx.mem.r_bstr(cli.cli_SetName.aptr)
        cli.cli_Module.aptr = 0
        ctx.process.set_current_dir(dup_lock.mem.addr)
        dos.cur_dir_lock = dup_lock

        # run command
        reg_d1 = packet >> 2
        code_start = ctx.process.shell_start
        log_dos.info("(Shell)SystemTagList: pc=%06x", code_start)
        ret_code = ami_run_command(ctx.process, code_start, 0, 0, stack_size, reg_d1)
        log_dos.info(
            "(Shell)SystemTagList returned: cmd='%s' tags=%s: ret_code=%d",
            cmd,
            tag_list,
            ret_code,
        )

        # shutdown
        cli.cli_CurrentInput.aptr = input_fhci
        cli.cli_StandardInput.aptr = input_fhsi
        cli.cli_Background.val = DOSFALSE
        cli.cli_Module.aptr = cur_module
        if output_fhci is not None:
            cli.cli_StandardOutput.aptr = output_fhci
        # Channels are closed by the dying shell
        ctx.mem.w_bstr(cli.cli_SetName.aptr, cur_setname)
        ctx.process.this_task.pr_CIS.aptr = input_fhci
        ctx.process.this_task.pr_COS.aptr = cur_out
        # infile = dos.file_mgr.get_by_b_addr(input_fhci >> 2,False)
        # infile.setbuf("")
        ctx.process.set_current_dir(current_dir)
        dos.cur_dir_lock = dos.lock_mgr.get_by_b_addr(current_dir >> 2)
        dos.setioerr(ctx, ret_code)
        return 0
    else:
        # parse "command line"
        cl = CommandLine()
        res = cl.parse_line(cmd)
        if res != cl.LINE_OK:
            log_dos.info("SystemTagList: error parsing command: '%s' -> %d", res)
            return 10  # RETURN_ERROR
        binary = cl.get_cmd()
        arg_str = cl.get_arg_str()
        log_dos.info("SystemTagList: bin='%s' arg_str='%s'", binary, arg_str[:-1])
        # fetch current dir for current process
        cur_proc = ctx.process
        cwd_lock = cur_proc.cwd_lock
        cwd = cur_proc.cwd
        # resolve the command's input/output: command line redirection wins
        # over the SYS_Input/SYS_Output handles Execute() forwarded
        redir = _resolve_redirection(dos, cwd_lock, cl, tag_list)
        if redir is None:
            return 10  # RETURN_ERROR
        input_fh, output_fh, redir_fhs = redir
        # create a process and run it...
        try:
            proc = Process(
                ctx,
                binary,
                arg_str,
                input_fh=input_fh,
                output_fh=output_fh,
                cwd=cwd,
                cwd_lock=cwd_lock,
            )
            if not proc.ok:
                log_dos.warning(
                    "SystemTagList: can't create process for '%s' args=%s",
                    binary,
                    arg_str,
                )
                return DOSTRUE
            return run_sub_process(ctx.scheduler, ctx.runner, proc)
        finally:
            # close only the handles opened for the redirection here
            for fh in redir_fhs:
                dos.file_mgr.close(fh)


def load_seg_list(dos, ctx, name, lock):
    """load a seglist by Amiga path and register it for UnLoadSeg"""
    b_addr = ctx.seg_loader.load_ami_seglist(name, lock)
    if b_addr == 0:
        log_dos.warning("LoadSeg: '%s' -> not found!", name)
        return 0
    # overlay seglists are returned as negative BPTR
    info = ctx.seg_loader.get_info(b_addr)
    if info.has_overlay():
        b_addr = -b_addr
    log_dos.info("LoadSeg: '%s' -> %06x", name, b_addr)
    dos.seg_lists[b_addr] = name
    return b_addr


def run_command(dos, ctx, b_addr, stack, args, length):
    if b_addr >= 0x80000000:
        b_addr -= 0x100000000
    if b_addr not in dos.seg_lists:
        raise VamosInternalError(
            "Trying to run unknown LoadSeg seg_list: b_addr=%06x" % b_addr
        )
    else:
        name = dos.seg_lists[b_addr]
    cmdline = ctx.mem.r_cstr(args)
    # push command line into input buffer so ReadArgs()/ReadItem() see it
    input_fh = ctx.process.get_input()
    input_fh.setbuf(cmdline)
    log_dos.info(
        "RunCommand: seglist=%06x(%s) stack=%d args=%s",
        b_addr,
        name,
        stack,
        cmdline,
    )
    # round up the stack
    stack = (stack + 3) & -4
    prog_start = (abs(b_addr) << 2) + 4
    # the running command sees its arguments in pr_Arguments and returns
    # through pr_ReturnAddr; both are restored afterwards (RKRM)
    proc = _ami_proc(ctx)
    old_args = old_return = None
    if proc is not None:
        old_args = proc.pr_Arguments.aptr
        old_return = proc.pr_ReturnAddr.aptr
        proc.pr_Arguments.aptr = args & 0xFFFFFFFF
        machine = getattr(ctx, "machine", None)
        if machine is not None:
            proc.pr_ReturnAddr.aptr = machine.get_run_exit_addr()
    try:
        ret_code = ami_run_command(ctx.process, prog_start, args, length, stack)
    finally:
        if proc is not None:
            proc.pr_Arguments.aptr = old_args
            proc.pr_ReturnAddr.aptr = old_return
        # flush leftover input, preserving IoErr (AROS does the same to fix
        # the AmigaOS C:Execute)
        io_err = getattr(dos, "io_err", 0)
        input_fh.setbuf("")
        dos.io_err = io_err
    return ret_code


def execute(dos, ctx, cmd, file, file2):
    """Execute(): run a command, temporarily redirecting input/output

    ``file``/``file2`` are BPTRs to the input/output file handles to use while
    the command runs (zero keeps the current handle). The command is run
    through ``_system_tag_list`` (so a test can replace it on the DOS lib).
    Returns DOSTRUE if the command could be found and started, DOSFALSE
    otherwise (never the command's return code).
    """
    # an empty command line with no handles creates a new interactive shell
    # (RKRM/AROS map this to "Run NewShell")
    if not cmd and not file and not file2:
        cmd = "Run NewShell"
    log_dos.info("Execute(%s, in=%s, out=%s)", cmd, file, file2)

    # forward the handles as SYS_Input/SYS_Output tags (AROS does the same)
    tags = []
    if file:
        tags.append((DosTag.SYS_Input, file))
    if file2:
        tags.append((DosTag.SYS_Output, file2))
    tag_list = TagList.alloc(ctx.alloc, *tags) if tags else None

    # keep the caller's handles visible to the non-native command runner
    proc = _ami_proc(ctx)
    old_cis = old_cos = None
    if proc is not None:
        old_cis = proc.pr_CIS.bptr
        old_cos = proc.pr_COS.bptr
        if file:
            proc.pr_CIS.bptr = file
        if file2:
            proc.pr_COS.bptr = file2
    try:
        result = dos._system_tag_list(ctx, cmd, tag_list)
    finally:
        if proc is not None:
            proc.pr_CIS.bptr = old_cis
            proc.pr_COS.bptr = old_cos
        if tag_list is not None:
            tag_list.free()
    # SystemTagList() returns 0 for success, otherwise the command result
    return DOSTRUE if result == 0 else DOSFALSE


def do_shell_method_tag_list(dos, ctx, method, tags):
    log_dos.warning(
        "DoShellMethodTagList(method=%d, tags=%s): not implemented",
        method,
        tags,
    )
    return 0


# ----- CliInit support -----


def cli_init(dos, ctx, dp):
    # Init style shells are not needed anymore
    log_dos.error("CliInit: not supported/needed!")
    return 0


def cli_init_newcli(dos, ctx, dp):
    # NewCLI style shells are not supported
    log_dos.error("CliInitNewcli: not supported/needed!")
    return 0


def cli_init_run(dos, ctx, dp):
    # check dos packet
    type = dp.type.val
    res1 = dp.res1.val
    res2 = dp.res2.val
    log_dos.info(
        "CliInitRun pkt@%08x type=%d res1=%d res2=%d", dp.addr, type, res1, res2
    )
    # run style
    if type != 0 and res1 == 0 and res2 == 0:
        # setup CLI with legacy CliInit
        return 0x80000008  # valid, and a async Run call.
    else:
        log_dos.warning(
            "CliInitRun: unsupported mode: type=%d res1=%d res2=%d",
            type,
            res1,
            res2,
        )
        return 0


__all__ = [
    "MAX_CLI",
    "child_proc_event",
    "cli_init",
    "cli_init_newcli",
    "cli_init_run",
    "create_new_proc",
    "create_proc",
    "do_shell_method_tag_list",
    "execute",
    "exit_process",
    "find_cli_proc",
    "get_arg_str",
    "get_console_task",
    "get_current_dir",
    "get_current_dir_name",
    "get_file_sys_task",
    "get_program_dir",
    "get_program_name",
    "get_prompt",
    "load_seg_list",
    "max_cli",
    "run_command",
    "set_arg_str",
    "set_console_task",
    "set_current_dir_name",
    "set_file_sys_task",
    "set_program_dir",
    "set_program_name",
    "set_prompt",
    "system_tag_list",
]


class CliMixin:
    """dos.library fd methods (HANDLER.md step 22m)."""

    def GetProgramName(self, ctx, buf_ptr, max_len):
        return get_program_name(self, ctx, buf_ptr, max_len)

    def GetProgramDir(self, ctx):
        return get_program_dir(self, ctx)

    def GetArgStr(self, ctx):
        return get_arg_str(self, ctx)

    def SystemTagList(self, ctx, cmd: CSTR, tag_list: TagList):
        return self._system_tag_list(ctx, cmd.get_str(), tag_list)

    def _system_tag_list(self, ctx, cmd, tag_list):
        return system_tag_list(self, ctx, cmd, tag_list)

    def _load_seg_list(self, ctx, name, lock):
        return load_seg_list(self, ctx, name, lock)

    def RunCommand(self, ctx, b_addr, stack, args, length):
        return run_command(self, ctx, b_addr, stack, args, length)

    def CliInit(self, ctx, dp: DosPacket):
        return cli_init(self, ctx, dp)

    def CliInitNewcli(self, ctx, dp: DosPacket):
        return cli_init_newcli(self, ctx, dp)

    def CliInitRun(self, ctx, dp: DosPacket):
        return cli_init_run(self, ctx, dp)

    def CreateNewProc(self, ctx, tags: TagList):
        return create_new_proc(self, ctx, tags)

    def SetCurrentDirName(self, ctx, str_addr):
        return set_current_dir_name(self, ctx, str_addr)

    def SetPrompt(self, ctx, str_addr):
        return set_prompt(self, ctx, str_addr)

    def GetFileSysTask(self, ctx):
        return get_file_sys_task(self, ctx)

    def SetFileSysTask(self, ctx, port):
        return set_file_sys_task(self, ctx, port)

    def CreateProc(self, ctx, name: CSTR, pri: LONG, segList: LONG, stackSize: LONG):
        return create_proc(
            self, ctx, name.get_str(), pri.val, segList.val, stackSize.val
        )

    def Exit(self, ctx, returnCode: LONG):
        return exit_process(self, ctx, returnCode.val)

    def Execute(self, ctx, string: CSTR, file: LONG, file2: LONG):
        return execute(self, ctx, string.get_str(), file.val, file2.val)

    def GetConsoleTask(self, ctx):
        return get_console_task(ctx)

    def SetConsoleTask(self, ctx, task: LONG):
        return set_console_task(ctx, task.val)

    def SetArgStr(self, ctx, string: CSTR):
        return set_arg_str(ctx, string.aptr)

    def FindCliProc(self, ctx, num: LONG):
        return find_cli_proc(ctx, num.val)

    def MaxCli(self, ctx):
        return max_cli(ctx)

    def GetCurrentDirName(self, ctx, buf: LONG, length: LONG):
        return get_current_dir_name(self, ctx, buf.val, length.val)

    def SetProgramName(self, ctx, name: CSTR):
        return set_program_name(self, ctx, name.get_str())

    def GetPrompt(self, ctx, buf: LONG, length: LONG):
        return get_prompt(self, ctx, buf.val, length.val)

    def SetProgramDir(self, ctx, lock: LONG):
        return set_program_dir(ctx, lock.val)

    def GetCurrentDir(self, ctx):
        return get_current_dir(ctx)

    def DoShellMethodTagList(self, ctx, method: LONG, tags: TagList):
        return do_shell_method_tag_list(self, ctx, method.val, tags)

    def _child_proc_event(self, event):
        """free a process made by CreateNewProc() once its task has ended"""
        return child_proc_event(self, event)
