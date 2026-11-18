"""dos.library process and CLI functions (RKRM AmigaDOS 3, "Process
Properties Accessor Functions" and "Creating and Terminating Processes").

Vamos gives every DOS process a CLI structure, so these accessors always
operate on a real shell context. ``CreateProc`` is a thin tag-list wrapper
around ``CreateNewProc`` and ``Exit`` ends the current m68k run through the
machine's normal exit trap. ``Execute`` reuses the ``SystemTagList`` command
runner.
"""

from amitools.vamos.libstructs import CLIStruct
from amitools.vamos.libtypes import DosTag, TagList
from amitools.vamos.log import log_dos
from amitools.vamos.machine.regs import REG_D0

from .Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_LINE_TOO_LONG,
    ERROR_NOT_IMPLEMENTED,
    ERROR_OBJECT_WRONG_TYPE,
)

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


def find_cli_proc(ctx, num):
    # Vamos has no process table with task numbers; report "not found"
    # without touching IoErr (as the AmigaDOS call does)
    log_dos.warning("FindCliProc(%d): no process table in vamos", num)
    return 0


def max_cli(ctx):
    return MAX_CLI


def get_current_dir_name(ctx, buf, max_len):
    cli = _cli(ctx)
    if cli is None:
        return DOSFALSE, ERROR_OBJECT_WRONG_TYPE
    name = ctx.mem.r_bstr(cli.cli_SetName.aptr)
    # the shell path always reports success, even if it was truncated
    return DOSTRUE, _copy_out(ctx, buf, max_len, name)


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


def set_program_dir(ctx, lock_bptr):
    proc = _ami_proc(ctx)
    if proc is None:
        return 0
    old = proc.pr_HomeDir.bptr
    proc.pr_HomeDir.bptr = lock_bptr & 0xFFFFFFFF
    return old


# ----- legacy Execute -----


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


__all__ = [
    "MAX_CLI",
    "create_proc",
    "execute",
    "exit_process",
    "find_cli_proc",
    "get_console_task",
    "get_current_dir",
    "get_current_dir_name",
    "get_prompt",
    "max_cli",
    "set_arg_str",
    "set_console_task",
    "set_program_dir",
    "set_program_name",
]
