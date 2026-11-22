"""dos.library process/CLI functions (Step 18)."""

from types import SimpleNamespace

import pytest

from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.error import VamosInternalError
from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_LINE_TOO_LONG,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_OBJECT_WRONG_TYPE,
)
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.dos.Cli import (
    _new_proc_tags,
    _resolve_child_dir,
    _resolve_child_fh,
)
from amitools.vamos.libstructs import CLIStruct, ProcessFlags, ProcessStruct
from amitools.vamos.libtypes import DosPacket, DosTag, TagList
from amitools.vamos.machine import Code, Machine, Runtime
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D0, REG_D1, REG_D2, REG_D3, REG_D4
from amitools.vamos.mem import MemoryAlloc

PROC_ADDR = 0x2000
CLI_ADDR = 0x1000
SETNAME_ADDR = 0x3000
CMDNAME_ADDR = 0x3100
PROMPT_ADDR = 0x3200
DEST_ADDR = 0x3300


def _cstr(mem, cpu, reg, text, str_addr=0x400):
    cpu.w_reg(reg, str_addr)
    mem.w_cstr(str_addr, text)
    return CSTR(cpu=cpu, reg=reg, mem=mem)


def _long(mem, cpu, reg, value):
    cpu.w_reg(reg, value)
    return LONG(cpu=cpu, reg=reg, mem=mem)


def _make_cli(mem):
    cli = CLIStruct(mem, CLI_ADDR)
    cli.cli_SetName.aptr = SETNAME_ADDR
    cli.cli_CommandName.aptr = CMDNAME_ADDR
    cli.cli_Prompt.aptr = PROMPT_ADDR
    mem.w_bstr(SETNAME_ADDR, "work:dir")
    mem.w_bstr(CMDNAME_ADDR, "prog")
    mem.w_bstr(PROMPT_ADDR, "1.SYS:> ")
    return cli


def _make_ctx(mem, cpu, cli=True):
    proc = ProcessStruct(mem, PROC_ADDR)
    proc.pr_CurrentDir.bptr = 12
    proc.pr_HomeDir.bptr = 34
    proc.pr_ConsoleTask.aptr = 0x111
    proc.pr_Arguments.aptr = 0x222
    cli_struct = _make_cli(mem)
    return SimpleNamespace(
        mem=mem,
        cpu=cpu,
        alloc=MemoryAlloc(mem),
        machine=SimpleNamespace(get_run_exit_addr=lambda: 0x400),
        process=SimpleNamespace(
            get_ami_process=lambda: proc,
            get_cli_struct=lambda: cli_struct.addr if cli else 0,
            this_task=proc,
            get_program_name=lambda: "myprog",
            get_home_dir=lambda: proc.pr_HomeDir.bptr,
        ),
    )


def lib_dos_cli_properties_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()

    assert lib.GetConsoleTask(ctx) == 0x111
    old = lib.SetConsoleTask(ctx, _long(mem, cpu, REG_D1, 0x333))
    assert old == 0x111
    assert ctx.process.this_task.pr_ConsoleTask.aptr == 0x333

    old = lib.SetArgStr(ctx, _cstr(mem, cpu, REG_D1, "arg1 arg2"))
    assert old == 0x222
    assert mem.r_cstr(ctx.process.this_task.pr_Arguments.aptr) == "arg1 arg2"

    assert lib.GetCurrentDir(ctx) == 12
    old = lib.SetProgramDir(ctx, _long(mem, cpu, REG_D1, 56))
    assert old == 34
    assert ctx.process.this_task.pr_HomeDir.bptr == 56


def lib_dos_cli_prompt_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()

    # full string fits
    buf = _long(mem, cpu, REG_D1, DEST_ADDR)
    length = _long(mem, cpu, REG_D2, 64)
    assert lib.GetCurrentDirName(ctx, buf, length) == DOSTRUE
    assert mem.r_cstr(DEST_ADDR) == "work:dir"
    assert lib.io_err == 0

    # truncated string still succeeds but sets IoErr
    buf = _long(mem, cpu, REG_D1, DEST_ADDR)
    length = _long(mem, cpu, REG_D2, 5)
    assert lib.GetCurrentDirName(ctx, buf, length) == DOSTRUE
    assert mem.r_cstr(DEST_ADDR) == "work"
    assert lib.io_err == ERROR_LINE_TOO_LONG

    buf = _long(mem, cpu, REG_D1, DEST_ADDR)
    length = _long(mem, cpu, REG_D2, 64)
    assert lib.GetPrompt(ctx, buf, length) == DOSTRUE
    assert mem.r_cstr(DEST_ADDR) == "1.SYS:> "
    assert lib.io_err == 0


def lib_dos_cli_prompt_no_shell_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu, cli=False)
    lib = DosLibrary()

    buf = _long(mem, cpu, REG_D1, DEST_ADDR)
    length = _long(mem, cpu, REG_D2, 32)
    assert lib.GetPrompt(ctx, buf, length) == DOSFALSE
    assert lib.io_err == ERROR_OBJECT_WRONG_TYPE
    assert lib.GetCurrentDirName(ctx, buf, length) == DOSFALSE
    assert lib.io_err == ERROR_OBJECT_WRONG_TYPE


def lib_dos_cli_program_name_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()

    long_name = "x" * 200
    assert lib.SetProgramName(ctx, _cstr(mem, cpu, REG_D1, long_name)) == DOSTRUE
    # cli_CommandName is limited to 104 bytes including the length byte
    assert mem.r_bstr(CMDNAME_ADDR) == "x" * 103
    assert lib.io_err == 0


def lib_dos_cli_find_and_max_test():
    lib = DosLibrary()
    lib.io_err = 17

    assert lib.FindCliProc(None, _long(MockMemory(), MockCPU(), REG_D1, 3)) == 0
    # FindCliProc does not touch IoErr
    assert lib.io_err == 17
    assert lib.MaxCli(None) == 256


def lib_dos_cli_execute_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()
    proc = ctx.process.this_task
    proc.pr_CIS.bptr = 11
    proc.pr_COS.bptr = 22
    seen = {}

    def run(call_ctx, cmd, tags):
        seen["cmd"] = cmd
        if tags:
            seen["tags"] = dict(tags.to_list(map_enum=DosTag, do_map=True))
        else:
            seen["tags"] = None
        seen["cis"] = proc.pr_CIS.bptr
        seen["cos"] = proc.pr_COS.bptr
        return seen.get("ret", 0)

    lib._system_tag_list = run
    cmd = _cstr(mem, cpu, REG_D1, "echo hi")
    file = _long(mem, cpu, REG_D2, 33)
    file2 = _long(mem, cpu, REG_D3, 44)
    # a zero result means the command could be started -> DOSTRUE
    assert lib.Execute(ctx, cmd, file, file2) == DOSTRUE
    assert seen == {
        "cmd": "echo hi",
        "tags": {DosTag.SYS_Input: 33, DosTag.SYS_Output: 44},
        "cis": 33,
        "cos": 44,
    }
    # the caller's handles are restored
    assert proc.pr_CIS.bptr == 11
    assert proc.pr_COS.bptr == 22

    # a non-zero result (command not found) -> DOSFALSE
    seen["ret"] = 5
    cmd = _cstr(mem, cpu, REG_D1, "echo hi")
    file = _long(mem, cpu, REG_D2, 0)
    file2 = _long(mem, cpu, REG_D3, 0)
    assert lib.Execute(ctx, cmd, file, file2) == DOSFALSE
    # zero handles keep the current input/output and add no tags
    assert seen == {"cmd": "echo hi", "tags": None, "cis": 11, "cos": 22, "ret": 5}

    # an empty command with no handles opens a new interactive shell
    del seen["ret"]
    cmd = _cstr(mem, cpu, REG_D1, "")
    file = _long(mem, cpu, REG_D2, 0)
    file2 = _long(mem, cpu, REG_D3, 0)
    assert lib.Execute(ctx, cmd, file, file2) == DOSTRUE
    assert seen["cmd"] == "Run NewShell"
    assert seen["tags"] is None
    assert ctx.alloc.is_all_free()


def lib_dos_cli_createproc_test():
    mem = MockMemory()
    cpu = MockCPU()
    alloc = MemoryAlloc(mem)
    lib = DosLibrary()
    parent = ProcessStruct(mem, PROC_ADDR)
    parent.window_ptr.aptr = 0x44
    ctx = SimpleNamespace(
        mem=mem,
        cpu=cpu,
        alloc=alloc,
        process=SimpleNamespace(proc=SimpleNamespace(addr=PROC_ADDR)),
    )
    captured = {}

    def create_new_proc(call_ctx, tag_list):
        captured["tags"] = dict(tag_list.to_list(map_enum=DosTag, do_map=True))
        return 0x1234

    lib.CreateNewProc = create_new_proc
    name = _cstr(mem, cpu, REG_D1, "child")
    pri = _long(mem, cpu, REG_D2, 5)
    seglist = _long(mem, cpu, REG_D3, 0x2222)
    stack = _long(mem, cpu, REG_D4, 8192)
    # CreateProc returns the process's pr_MsgPort, not the Process struct
    assert lib.CreateProc(ctx, name, pri, seglist, stack) == (
        ProcessStruct(mem, 0x1234).msg_port.addr
    )
    tags = captured["tags"]
    assert tags[DosTag.NP_SegList] == 0x2222
    assert tags[DosTag.NP_StackSize] == 8192
    assert tags[DosTag.NP_Priority] == 5
    assert mem.r_cstr(tags[DosTag.NP_Name]) == "child"
    # RKRM: CreateProc copies the caller's pr_WindowPtr unconditionally (it
    # does not use CreateNewProc's NULL/-1 default rule)
    assert tags[DosTag.NP_WindowPtr] == 0x44
    # AOS 3.x compat: keep the seglist, the dirs and the inherited handles
    assert tags[DosTag.NP_FreeSegList] == 0
    assert tags[DosTag.NP_CurrentDir] == 0
    assert tags[DosTag.NP_HomeDir] == 0
    assert tags[DosTag.NP_Input] == 0
    assert tags[DosTag.NP_Output] == 0
    assert tags[DosTag.NP_CloseInput] == 0
    assert tags[DosTag.NP_CloseOutput] == 0

    # a failing CreateNewProc yields a NULL msg port
    lib.CreateNewProc = lambda call_ctx, tag_list: 0
    name = _cstr(mem, cpu, REG_D1, "child")
    pri = _long(mem, cpu, REG_D2, 5)
    seglist = _long(mem, cpu, REG_D3, 0x2222)
    stack = _long(mem, cpu, REG_D4, 8192)
    assert lib.CreateProc(ctx, name, pri, seglist, stack) == 0
    assert alloc.is_all_free()

    # NULL seglist cannot create a process
    name = _cstr(mem, cpu, REG_D1, "child")
    pri = _long(mem, cpu, REG_D2, 5)
    seglist = _long(mem, cpu, REG_D3, 0)
    stack = _long(mem, cpu, REG_D4, 8192)
    assert lib.CreateProc(ctx, name, pri, seglist, stack) == 0
    assert alloc.is_all_free()


def lib_dos_cli_exit_test():
    machine = Machine(use_labels=False)
    try:
        mem = machine.get_mem()
        cpu = machine.get_cpu()
        alloc = MemoryAlloc.for_machine(machine)
        runtime = Runtime(machine)
        lib = DosLibrary()
        ctx = SimpleNamespace(machine=machine, mem=mem, cpu=cpu, alloc=alloc)

        code = _long(mem, cpu, REG_D1, 7)
        lib.Exit(ctx, code)
        assert cpu.r_pc() == machine.get_run_exit_addr()
        assert cpu.r_reg(REG_D0) == 7

        # entering the exit trap ends the run and keeps the return code in D0
        run_state = runtime.run(Code(pc=cpu.r_pc(), sp=0x2000, get_regs=[REG_D0]))
        assert run_state.exit is True
        assert run_state.regs[REG_D0] == 7
        assert run_state.mach_error is None
    finally:
        machine.cleanup()


def lib_dos_cli_deviceproc_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = SimpleNamespace(mem=mem, cpu=cpu, process=None)
    lib = DosLibrary()
    lib.path_mgr = SimpleNamespace(
        ami_abs_path=lambda lock, name: "work:",
        ami_volume_of_path=lambda path: "work",
    )
    lib.get_current_dir = lambda call_ctx: None
    lib.handler_mgr = SimpleNamespace(
        get_dispatcher=lambda name: SimpleNamespace(port=0x4321)
    )

    assert lib.DeviceProc(ctx, _cstr(mem, cpu, REG_D1, "work:")) == 0x4321

    # unknown handler
    lib.handler_mgr = SimpleNamespace(get_dispatcher=lambda name: None)
    assert lib.DeviceProc(ctx, _cstr(mem, cpu, REG_D1, "work:")) == 0
    assert lib.io_err == ERROR_OBJECT_NOT_FOUND

    # NULL name
    cpu.w_reg(REG_D1, 0)
    assert lib.DeviceProc(ctx, CSTR(cpu=cpu, reg=REG_D1, mem=mem)) == 0


def lib_dos_cli_file_sys_task_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()

    # an unset file system task reads back as NULL
    assert lib.GetFileSysTask(ctx) == 0

    # SetFileSysTask is a void call but updates the process field
    assert lib.SetFileSysTask(ctx, 0x1234) is None
    assert ctx.process.this_task.pr_FileSystemTask.aptr == 0x1234
    assert lib.GetFileSysTask(ctx) == 0x1234

    # and it can be cleared again
    lib.SetFileSysTask(ctx, 0)
    assert ctx.process.this_task.pr_FileSystemTask.aptr == 0
    assert lib.GetFileSysTask(ctx) == 0


def lib_dos_cli_get_program_name_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()
    lib.io_err = 0

    # name fits into the buffer
    assert lib.GetProgramName(ctx, DEST_ADDR, 32) == DOSTRUE
    assert mem.r_cstr(DEST_ADDR) == "myprog"
    assert lib.io_err == 0

    # a too small buffer truncates and reports IoErr
    assert lib.GetProgramName(ctx, DEST_ADDR, 4) == DOSFALSE
    assert mem.r_cstr(DEST_ADDR) == "mypr"
    assert lib.io_err == ERROR_LINE_TOO_LONG

    # an empty program name is copied as an empty string and leaves IoErr alone
    ctx.process.get_program_name = lambda: ""
    lib.io_err = 0
    assert lib.GetProgramName(ctx, DEST_ADDR, 32) == DOSTRUE
    assert mem.r_cstr(DEST_ADDR) == ""
    assert lib.io_err == 0

    # a missing (None) program name is not handled by the library
    ctx.process.get_program_name = lambda: None
    with pytest.raises(TypeError):
        lib.GetProgramName(ctx, DEST_ADDR, 32)


def lib_dos_cli_get_program_dir_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()

    # pr_HomeDir is bptr 34 -> b_addr 8, so the lock manager is asked for 8
    lock = SimpleNamespace(b_addr=8)
    asked = []

    def get_by_b_addr(b_addr):
        asked.append(b_addr)
        return lock if b_addr == 8 else None

    lib.lock_mgr = SimpleNamespace(get_by_b_addr=get_by_b_addr)
    assert lib.GetProgramDir(ctx) == 8
    assert asked == [8]

    # no matching lock yields a NULL dir
    lib.lock_mgr = SimpleNamespace(get_by_b_addr=lambda b_addr: None)
    assert lib.GetProgramDir(ctx) == 0


def lib_dos_cli_set_prompt_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()

    mem.w_cstr(DEST_ADDR, "new prompt> ")
    assert lib.SetPrompt(ctx, DEST_ADDR) == DOSTRUE
    assert mem.r_bstr(PROMPT_ADDR) == "new prompt> "

    # cli_Prompt is limited to 59 characters
    mem.w_cstr(DEST_ADDR, "p" * 100)
    assert lib.SetPrompt(ctx, DEST_ADDR) == DOSTRUE
    assert mem.r_bstr(PROMPT_ADDR) == "p" * 59


def lib_dos_cli_system_tag_list_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()
    seen = {}

    def run(call_ctx, cmd, tags):
        seen["ctx"] = call_ctx
        seen["cmd"] = cmd
        seen["tags"] = tags
        return 0x80000001

    lib._system_tag_list = run
    mem.w32(0x3900, 0)  # TAG_DONE
    tag_list = TagList(mem, 0x3900)

    cmd = _cstr(mem, cpu, REG_D1, "dir work:")
    assert lib.SystemTagList(ctx, cmd, tag_list) == 0x80000001
    assert seen["ctx"] is ctx
    assert seen["cmd"] == "dir work:"
    assert seen["tags"] is tag_list

    # an empty command is decoded to "" and forwarded unchanged
    cmd = _cstr(mem, cpu, REG_D1, "")
    assert lib.SystemTagList(ctx, cmd, tag_list) == 0x80000001
    assert seen["cmd"] == ""


def lib_dos_cli_init_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()

    dp = DosPacket(mem, 0x3800)
    dp.type.val = 1
    dp.res1.val = 0
    dp.res2.val = 0

    # both legacy init styles are stubbed out and report failure
    assert lib.CliInit(ctx, dp) == 0
    assert lib.CliInitNewcli(ctx, dp) == 0
    # the packet is left untouched
    assert dp.type.val == 1
    assert dp.res1.val == 0
    assert dp.res2.val == 0


def lib_dos_cli_init_run_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()

    dp = DosPacket(mem, 0x3800)

    # RUN style: type != 0 and res1/res2 zero -> async Run call
    dp.type.val = 1
    dp.res1.val = 0
    dp.res2.val = 0
    assert lib.CliInitRun(ctx, dp) == 0x80000008

    # res1 set -> unsupported
    dp.res1.val = 1
    assert lib.CliInitRun(ctx, dp) == 0

    # res2 set -> unsupported
    dp.res1.val = 0
    dp.res2.val = 1
    assert lib.CliInitRun(ctx, dp) == 0

    # type 0 (system/nil packet) -> unsupported
    dp.type.val = 0
    dp.res2.val = 0
    assert lib.CliInitRun(ctx, dp) == 0


def lib_dos_cli_extended_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()

    # ExtendedCli is accepted but ignored
    assert lib.ExtendedCli(ctx) == 0


def lib_dos_cli_check_signal_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    ctx.exec_lib = SimpleNamespace(
        exec_lib=SimpleNamespace(this_task=SimpleNamespace(aptr=PROC_ADDR)),
    )
    lib = DosLibrary()

    # vamos never reports a pending CLI signal, so every mask reads clear
    assert lib.CheckSignal(ctx, 0) == 0
    assert lib.CheckSignal(ctx, 0x00000001) == 0
    assert lib.CheckSignal(ctx, 0xFFFFFFFF) == 0


def lib_dos_cli_struct_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()

    # Cli() returns the CLI structure of the process
    assert lib.Cli(ctx) == CLI_ADDR


def lib_dos_cli_set_current_dir_name_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()

    mem.w_cstr(DEST_ADDR, "newdir")
    assert lib.SetCurrentDirName(ctx, DEST_ADDR) == DOSTRUE
    assert mem.r_bstr(SETNAME_ADDR) == "newdir"

    # cli_SetName is limited to 79 characters
    mem.w_cstr(DEST_ADDR, "d" * 100)
    assert lib.SetCurrentDirName(ctx, DEST_ADDR) == DOSTRUE
    assert mem.r_bstr(SETNAME_ADDR) == "d" * 79


def lib_dos_cli_run_command_test(monkeypatch):
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()
    lib.seg_lists = {0x10: "prog"}

    input_fh = SimpleNamespace(buf=None)
    input_fh.setbuf = lambda s: setattr(input_fh, "buf", s)
    ctx.process.get_input = lambda: input_fh
    mem.w_cstr(DEST_ADDR, "arg1")

    calls = []

    def fake_run(proc, prog_start, args, length, stack):
        ami_proc = ctx.process.get_ami_process()
        calls.append(
            (
                proc,
                prog_start,
                args,
                length,
                stack,
                ami_proc.pr_Arguments.aptr,
                ami_proc.pr_ReturnAddr.aptr,
            )
        )
        # the command sets its own IoErr; the flush must preserve it
        lib.io_err = 42
        return 7

    monkeypatch.setattr("amitools.vamos.lib.dos.Cli.ami_run_command", fake_run)
    assert lib.RunCommand(ctx, 0x10, 8, DEST_ADDR, 4) == 7
    # the stack is rounded up and the seglist is resolved to its program start;
    # pr_Arguments/pr_ReturnAddr are set while the command runs
    assert calls == [(ctx.process, (0x10 << 2) + 4, DEST_ADDR, 4, 8, DEST_ADDR, 0x400)]
    # the command line is pushed and cleared again
    assert input_fh.buf == ""
    # both process fields are restored, the command's IoErr survives the flush
    assert ctx.process.this_task.pr_Arguments.aptr == 0x222
    assert ctx.process.this_task.pr_ReturnAddr.aptr == 0
    assert lib.io_err == 42


def lib_dos_cli_run_command_unknown_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    lib = DosLibrary()
    lib.seg_lists = {}

    with pytest.raises(VamosInternalError):
        lib.RunCommand(ctx, 0x10, 0, DEST_ADDR, 0)


def _new_proc_ctx(mem, alloc, parent_addr=0):
    if parent_addr:
        exec_lib = SimpleNamespace(
            exec_lib=SimpleNamespace(
                this_task=SimpleNamespace(aptr=parent_addr),
            ),
        )
    else:
        exec_lib = None
    return SimpleNamespace(mem=mem, alloc=alloc, exec_lib=exec_lib, process=None)


def lib_dos_cli_new_proc_defaults_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    ctx = _new_proc_ctx(mem, alloc)

    tags = TagList.alloc(alloc, (DosTag.NP_Entry, 0x4000))
    p = _new_proc_tags(ctx, tags)
    assert p["name"] == "New Process"
    assert p["entry_pc"] == 0x4000
    assert p["seglist_bptr"] == 0
    assert p["stack_size"] == 4000
    assert p["priority"] == 0
    # absent dir tags stay None: _spawn resolves them by duplicating the
    # caller's locks (or ZERO for a task)
    assert p["current_dir"] is None
    assert p["home_dir"] is None
    assert p["console_task"] == 0
    # a task (no parent) gets a NULL window pointer (RKRM)
    assert p["window_ptr"] == 0
    # handles are not resolved here: _spawn opens the NIL: defaults
    assert p["input_fh"] is None
    assert p["output_fh"] is None
    assert p["error_fh"] is None
    assert p["arguments"] is None
    # close input/output default to TRUE; error and free-seglist to FALSE
    assert p["flags"] & ProcessFlags.PRF_CLOSEINPUT
    assert p["flags"] & ProcessFlags.PRF_CLOSEOUTPUT
    assert not (p["flags"] & ProcessFlags.PRF_CLOSEERROR)
    assert not (p["flags"] & ProcessFlags.PRF_FREESEGLIST)
    assert not (p["flags"] & ProcessFlags.PRF_NOTIFYONDEATH)
    assert not (p["flags"] & ProcessFlags.PRF_FREEARGS)
    tags.free()


def lib_dos_cli_new_proc_tags_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    ctx = _new_proc_ctx(mem, alloc)

    name = alloc.alloc_cstr("myproc")
    args = alloc.alloc_cstr("arg1 arg2")
    tags = TagList.alloc(
        alloc,
        (DosTag.NP_Entry, 0x4000),
        (DosTag.NP_Name, name.addr),
        (DosTag.NP_StackSize, 8192),
        (DosTag.NP_Priority, 7),
        (DosTag.NP_CurrentDir, 0x11),
        (DosTag.NP_HomeDir, 0x22),
        (DosTag.NP_Input, 0x33),
        (DosTag.NP_Output, 0x44),
        (DosTag.NP_Error, 0x55),
        (DosTag.NP_ConsoleTask, 0x66),
        (DosTag.NP_WindowPtr, 0x77),
        (DosTag.NP_Arguments, args.addr),
        (DosTag.NP_NotifyOnDeath, 1),
        (DosTag.NP_ExitCode, 0x88),
        (DosTag.NP_ExitData, 0x99),
        (DosTag.NP_FreeSegList, 0),
        (DosTag.NP_CloseInput, 0),
        (DosTag.NP_CloseOutput, 0),
        (DosTag.NP_CloseError, 0),
        (DosTag.NP_UserData, 0xAA),
    )
    p = _new_proc_tags(ctx, tags)
    assert p["name"] == "myproc"
    assert p["entry_pc"] == 0x4000
    assert p["stack_size"] == 8192
    assert p["priority"] == 7
    assert p["current_dir"] == 0x11
    assert p["home_dir"] == 0x22
    assert p["input_fh"] == 0x33
    assert p["output_fh"] == 0x44
    assert p["error_fh"] == 0x55
    assert p["console_task"] == 0x66
    assert p["window_ptr"] == 0x77
    assert p["arguments"] == "arg1 arg2"
    assert p["exit_code"] == 0x88
    assert p["exit_data"] == 0x99
    assert p["user_data"] == 0xAA
    assert p["notify_on_death"] == 1
    # the explicit close/seglist/arguments flags are honored
    assert not (p["flags"] & ProcessFlags.PRF_CLOSEINPUT)
    assert not (p["flags"] & ProcessFlags.PRF_CLOSEOUTPUT)
    assert not (p["flags"] & ProcessFlags.PRF_CLOSEERROR)
    assert not (p["flags"] & ProcessFlags.PRF_FREESEGLIST)
    assert p["flags"] & ProcessFlags.PRF_NOTIFYONDEATH
    assert p["flags"] & ProcessFlags.PRF_FREEARGS
    tags.free()
    ctx.alloc.free_cstr(name)
    ctx.alloc.free_cstr(args)


def lib_dos_cli_new_proc_seglist_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    ctx = _new_proc_ctx(mem, alloc)

    tags = TagList.alloc(alloc, (DosTag.NP_SegList, 0x1234))
    p = _new_proc_tags(ctx, tags)
    # the entry is the first segment of the seglist
    assert p["entry_pc"] == (0x1234 << 2) + 4
    assert p["seglist_bptr"] == 0x1234
    tags.free()


def lib_dos_cli_new_proc_missing_entry_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    ctx = _new_proc_ctx(mem, alloc)

    tags = TagList.alloc(alloc, (DosTag.NP_StackSize, 4096))
    assert _new_proc_tags(ctx, tags) is None
    tags.free()


def lib_dos_cli_new_proc_inherit_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    parent = ProcessStruct(mem, PROC_ADDR)
    parent.task.node.pri.val = 9
    parent.current_dir.bptr = 0x11
    parent.home_dir.bptr = 0x22
    parent.console_task.aptr = 0x33
    parent.window_ptr.aptr = 0x44
    ctx = _new_proc_ctx(mem, alloc, parent_addr=PROC_ADDR)

    tags = TagList.alloc(alloc, (DosTag.NP_Entry, 0x4000))
    p = _new_proc_tags(ctx, tags)
    assert p["parent_addr"] == PROC_ADDR
    # priority defaults to 0 (RKRM); the console task is inherited from the
    # parent, while the absent dir tags stay None and are duplicated from the
    # parent by _spawn()
    assert p["priority"] == 0
    assert p["current_dir"] is None
    assert p["home_dir"] is None
    assert p["console_task"] == 0x33
    # the parent's window pointer is neither NULL nor -1, so the child gets NULL
    assert p["window_ptr"] == 0
    tags.free()


def lib_dos_cli_new_proc_window_ptr_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    parent = ProcessStruct(mem, PROC_ADDR)
    ctx = _new_proc_ctx(mem, alloc, parent_addr=PROC_ADDR)

    # absent tag, parent window NULL -> copied
    parent.window_ptr.aptr = 0
    tags = TagList.alloc(alloc, (DosTag.NP_Entry, 0x4000))
    assert _new_proc_tags(ctx, tags)["window_ptr"] == 0
    tags.free()

    # absent tag, parent window -1 -> copied
    parent.window_ptr.aptr = 0xFFFFFFFF
    tags = TagList.alloc(alloc, (DosTag.NP_Entry, 0x4000))
    assert _new_proc_tags(ctx, tags)["window_ptr"] == 0xFFFFFFFF
    tags.free()

    # absent tag, parent window other -> NULL
    parent.window_ptr.aptr = 0x44
    tags = TagList.alloc(alloc, (DosTag.NP_Entry, 0x4000))
    assert _new_proc_tags(ctx, tags)["window_ptr"] == 0
    tags.free()

    # an explicit tag is installed as-is (even a real window pointer)
    tags = TagList.alloc(alloc, (DosTag.NP_Entry, 0x4000), (DosTag.NP_WindowPtr, 0x44))
    assert _new_proc_tags(ctx, tags)["window_ptr"] == 0x44
    tags.free()


def lib_dos_cli_new_proc_resolve_dir_test():
    class FakeLock:
        def __init__(self, b_addr):
            self.b_addr = b_addr

    class FakeLockMgr:
        def __init__(self, parent_lock=None, dup_addr=0x99):
            self.parent_lock = parent_lock
            self.dup_addr = dup_addr
            self.dups = 0

        def get_by_b_addr(self, b_addr):
            return self.parent_lock

        def dup_lock(self, lock):
            self.dups += 1
            return FakeLock(self.dup_addr) if self.dup_addr is not None else None

    # an explicit tag lock is absorbed by the child (no dup)
    mgr = FakeLockMgr()
    dos = SimpleNamespace(lock_mgr=mgr)
    assert _resolve_child_dir(dos, 0x11, 0x22, "current dir") == (0x11, True)
    assert mgr.dups == 0

    # an explicit ZERO is kept and owns nothing
    assert _resolve_child_dir(dos, 0, 0x22, "current dir") == (0, False)

    # an absent tag duplicates the caller's lock
    mgr = FakeLockMgr(parent_lock=FakeLock(0x22))
    dos = SimpleNamespace(lock_mgr=mgr)
    assert _resolve_child_dir(dos, None, 0x22, "current dir") == (0x99, True)
    assert mgr.dups == 1

    # no caller lock (a task) -> ZERO
    mgr = FakeLockMgr()
    dos = SimpleNamespace(lock_mgr=mgr)
    assert _resolve_child_dir(dos, None, 0, "current dir") == (0, False)
    assert mgr.dups == 0

    # a failed DupLock also yields ZERO and owns nothing
    mgr = FakeLockMgr(parent_lock=FakeLock(0x22), dup_addr=None)
    dos = SimpleNamespace(lock_mgr=mgr)
    assert _resolve_child_dir(dos, None, 0x22, "current dir") == (0, False)
    assert mgr.dups == 1


def lib_dos_cli_new_proc_resolve_fh_test():
    class FakeFH:
        b_addr = 0x99

    class FakeFileMgr:
        def __init__(self):
            self.opened = []

        def open(self, lock, path, mode):
            self.opened.append((path, mode))
            return FakeFH()

    dos = SimpleNamespace(file_mgr=FakeFileMgr())
    # an absent tag opens the NIL: default
    assert _resolve_child_fh(dos, None, "r", "input") == 0x99
    assert dos.file_mgr.opened == [("NIL:", "r")]
    # an explicit 0 (BNULL) is kept: no NIL: open (AROS behaviour)
    assert _resolve_child_fh(dos, 0, "r", "input") == 0
    assert dos.file_mgr.opened == [("NIL:", "r")]
    # a caller supplied handle is kept
    assert _resolve_child_fh(dos, 0x33, "r", "input") == 0x33
    assert dos.file_mgr.opened == [("NIL:", "r")]
