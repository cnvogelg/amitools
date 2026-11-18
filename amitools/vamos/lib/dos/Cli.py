"""dos.library process and CLI functions (RKRM AmigaDOS 3, "Process
Properties Accessor Functions" and "Creating and Terminating Processes").

Vamos gives every DOS process a CLI structure, so these accessors always
operate on a real shell context. ``CreateProc`` is a thin tag-list wrapper
around ``CreateNewProc`` and ``Exit`` ends the current m68k run through the
machine's normal exit trap. ``Execute`` reuses the ``SystemTagList`` command
runner.
"""

from amitools.vamos.dos import run_command as ami_run_command
from amitools.vamos.dos import run_sub_process
from amitools.vamos.error import VamosInternalError
from amitools.vamos.libstructs import CLIStruct, MsgPortFlags, ProcessStruct, TaskState
from amitools.vamos.libtypes import DosTag, TagList
from amitools.vamos.log import log_dos
from amitools.vamos.machine.regs import REG_A0, REG_D0

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

# the AmigaDOS V36 process table size returned by MaxCli()
MAX_CLI = 256


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
    tags = [
        (DosTag.NP_SegList, seglist & 0xFFFFFFFF),
        (DosTag.NP_StackSize, stack_size & 0xFFFFFFFF),
        (DosTag.NP_Priority, pri & 0xFFFFFFFF),
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
    log_dos.info("CreateProc(%s, pri=%d) -> %06x", name, pri, proc_addr)
    return proc_addr


def _new_proc_tags(ctx, tags):
    """read the ``NP_*`` tag list into a parameter set (``None`` on error)"""
    tag_list = tags.to_list(map_enum=DosTag, do_map=True)
    log_dos.info("CreateNewProc: tags=%s", tag_list)

    entry_pc = tags.get_tag_data(DosTag.NP_Entry, 0)
    seglist_bptr = tags.get_tag_data(DosTag.NP_SegList, 0)
    stack_size = tags.get_tag_data(DosTag.NP_StackSize, 4096)
    name_ptr = tags.get_tag_data(DosTag.NP_Name, 0)
    priority = tags.get_tag_data(DosTag.NP_Priority, 0)
    current_dir = tags.get_tag_data(DosTag.NP_CurrentDir, 0)
    home_dir = tags.get_tag_data(DosTag.NP_HomeDir, 0)
    input_fh = tags.get_tag_data(DosTag.NP_Input, 0)
    output_fh = tags.get_tag_data(DosTag.NP_Output, 0)

    name = ctx.mem.r_cstr(name_ptr) if name_ptr != 0 else "child_process"
    if entry_pc == 0 and seglist_bptr == 0:
        log_dos.warning("CreateNewProc: no NP_Entry or NP_SegList")
        return None
    if entry_pc == 0 and seglist_bptr != 0:
        seg_addr = seglist_bptr << 2
        entry_pc = seg_addr + 4

    log_dos.info(
        "CreateNewProc: name=%s entry=%06x stack=%d pri=%d",
        name,
        entry_pc,
        stack_size,
        priority,
    )
    return {
        "name": name,
        "entry_pc": entry_pc,
        "seglist_bptr": seglist_bptr,
        "stack_size": stack_size,
        "priority": priority,
        "current_dir": current_dir,
        "home_dir": home_dir,
        "input_fh": input_fh,
        "output_fh": output_fh,
    }


def _spawn(dos, ctx, p):
    """create and schedule the child process described by ``p``"""
    # the child is a process of its own: the scheduler runs it beside
    # its parent, and it is freed once its task ends (_child_proc_event)
    child = dos.create_child_process(
        ctx,
        p["name"],
        stack_size=p["stack_size"],
        start_pc=p["entry_pc"],
        start_regs={REG_D0: 0, REG_A0: 0},
    )
    proc = child.proc
    task = proc.task
    stack = child.get_stack()
    task.node.pri.val = p["priority"]
    task.sp_reg.aptr = stack.get_initial_sp()
    task.sp_lower.aptr = stack.get_lower()
    task.sp_upper.aptr = stack.get_upper()
    proc.stack_size.val = stack.get_size()
    proc.stack_base.bptr = stack.get_lower() >> 2
    proc.seg_list.bptr = p["seglist_bptr"]
    proc.glob_vec.aptr = 0xFFFFFFFF
    proc.current_dir.bptr = p["current_dir"]
    proc.home_dir.bptr = p["home_dir"]
    proc.window_ptr.aptr = 0xFFFFFFFF

    input_fh = p["input_fh"]
    output_fh = p["output_fh"]
    if input_fh == 0 or output_fh == 0:
        parent_proc = ctx.exec_lib.exec_lib.this_task.aptr
        if parent_proc != 0:
            parent = ProcessStruct(ctx.mem, parent_proc)
            if input_fh == 0:
                input_fh = parent.cis.bptr
            if output_fh == 0:
                output_fh = parent.cos.bptr
    proc.cis.bptr = input_fh
    proc.cos.bptr = output_fh

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
        "CreateNewProc: created process %06x entry=%06x port=%06x",
        proc.addr,
        p["entry_pc"],
        port_addr,
    )
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


def get_current_dir_name(ctx, buf, max_len):
    cli = _cli(ctx)
    if cli is None:
        return DOSFALSE, ERROR_OBJECT_WRONG_TYPE
    name = ctx.mem.r_bstr(cli.cli_SetName.aptr)
    # the shell path always reports success, even if it was truncated
    return DOSTRUE, _copy_out(ctx, buf, max_len, name)


def set_current_dir_name(dos, ctx, str_addr):
    string = ctx.mem.r_cstr(str_addr)[:79]
    cli_addr = dos.Cli(ctx)
    cli = CLIStruct(ctx.mem, cli_addr)
    setaddr = cli.cli_SetName.aptr
    ctx.mem.w_bstr(setaddr, string)
    return DOSTRUE


def set_program_name(ctx, name):
    cli = _cli(ctx)
    if cli is None:
        return DOSFALSE, ERROR_OBJECT_WRONG_TYPE
    # cli_CommandName has a fixed 104 byte buffer
    ctx.mem.w_bstr(cli.cli_CommandName.aptr, (name or "")[:103])
    return DOSTRUE, 0


def get_prompt(ctx, buf, max_len):
    cli = _cli(ctx)
    if cli is None:
        return DOSFALSE, ERROR_OBJECT_WRONG_TYPE
    prompt = ctx.mem.r_bstr(cli.cli_Prompt.aptr)
    return DOSTRUE, _copy_out(ctx, buf, max_len, prompt)


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


def system_tag_list(dos, ctx, cmd, tag_list):
    log_dos.info("SystemTagList: cmd=%s tags=%s ctx=%s", cmd, tag_list, ctx)
    # cmd is at this point a full string of commands to execute.
    # If we're running from the Amiga shell, forward this to the shell
    # anyhow.
    if ctx.process.is_native_shell():
        cli_addr = ctx.process.get_cli_struct()
        cli = CLIStruct(ctx.mem, cli_addr)
        new_input = dos.file_mgr.open(None, "NIL:", "r")
        if new_input == None:
            log_dos.warning(
                "SystemTagList: can't create new input file handle for SystemTagList('%s')",
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
        cur_lock = dos.lock_mgr.get_by_b_addr(current_dir >> 2)
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
        if output_fhci != None:
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
        # TODO: redirs
        binary = cl.get_cmd()
        arg_str = cl.get_arg_str()
        log_dos.info("SystemTagList: bin='%s' arg_str='%s'", binary, arg_str[:-1])
        # fetch current dir for current process
        cur_proc = ctx.process
        cwd_lock = cur_proc.cwd_lock
        cwd = cur_proc.cwd
        # create a process and run it...
        proc = Process(ctx, binary, arg_str, cwd=cwd, cwd_lock=cwd_lock)
        if not proc.ok:
            log_dos.warning(
                "SystemTagList: can't create process for '%s' args=%s",
                binary,
                arg_str,
            )
            return DOSTRUE
        return run_sub_process(ctx.scheduler, ctx.runner, proc)


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
    if not b_addr in dos.seg_lists:
        raise VamosInternalError(
            "Trying to run unknown LoadSeg seg_list: b_addr=%06x" % b_addr
        )
    else:
        name = dos.seg_lists[b_addr]
    fh = ctx.process.get_input()
    cmdline = ctx.mem.r_cstr(args)
    # push command line into input buffer
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
    ret_code = ami_run_command(ctx.process, prog_start, args, length, stack)
    # clear input
    input_fh.setbuf("")
    return ret_code


def execute(dos, ctx, cmd, file, file2, run):
    """Execute(): run a command, temporarily redirecting input/output

    ``file``/``file2`` are BPTRs to the input/output file handles to use while
    the command runs (zero keeps the current handle). ``run`` is the
    ``SystemTagList`` command runner.
    """
    if not cmd:
        return DOSFALSE
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
        log_dos.info("Execute(%s, in=%s, out=%s)", cmd, file, file2)
        return run(ctx, cmd)
    finally:
        if proc is not None:
            proc.pr_CIS.bptr = old_cis
            proc.pr_COS.bptr = old_cos


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
    "cli_init",
    "cli_init_newcli",
    "cli_init_run",
    "create_new_proc",
    "create_proc",
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
