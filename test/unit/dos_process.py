"""DOS process classes: the ``self.proc`` dedup and ``BinProcess``.

Step 2 of the shell refactor folded the old ``self.this_task`` ProcessStruct
view into ``self.proc`` (the ``libtypes.Process`` allocated by ``DosProcess``)
and dropped the duplicated dir/var/cli accessors.  Step 3 added ``BinProcess``
for the single-binary path.  These tests pin both down without needing a full
vamos context.
"""

from types import SimpleNamespace

from amitools.vamos.lib.dos.Process import BinProcess, ProcessBase
from amitools.vamos.libstructs import CLIStruct
from amitools.vamos.machine import (
    Machine,
    REG_A0,
    REG_A2,
    REG_A5,
    REG_A6,
    REG_D0,
    REG_D1,
    REG_D2,
)
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.task import DosProcess


class _Proc:
    def __init__(self):
        self.pr_CIS = SimpleNamespace(aptr=0)
        self.pr_COS = SimpleNamespace(aptr=0)
        self.pr_Arguments = SimpleNamespace(aptr=0)


class _FileMgr:
    def __init__(self):
        self.files = {0x10: "in", 0x20: "out"}

    def get_by_b_addr(self, b_addr):
        return self.files.get(b_addr)


def _make_process():
    proc = _Proc()
    file_mgr = _FileMgr()
    ctx = SimpleNamespace(dos_lib=SimpleNamespace(file_mgr=file_mgr))
    p = ProcessBase.__new__(ProcessBase)
    p.ctx = ctx
    p.proc = proc
    return p, proc, file_mgr


def dos_process_this_task_is_proc_test():
    # this_task is only an alias for the already allocated self.proc struct
    p, proc, _ = _make_process()
    assert p.this_task is proc


def dos_process_stream_accessors_test():
    p, proc, file_mgr = _make_process()
    in_fh = SimpleNamespace(b_addr=0x10)
    out_fh = SimpleNamespace(b_addr=0x20)

    p.set_input(in_fh)
    assert proc.pr_CIS.aptr == 0x10 << 2
    p.set_output(out_fh)
    assert proc.pr_COS.aptr == 0x20 << 2

    assert p.get_input() == "in"
    assert p.get_output() == "out"

    # BNULL clears the field instead of writing a handle
    p.set_input(None)
    p.set_output(None)
    assert proc.pr_CIS.aptr == 0
    assert proc.pr_COS.aptr == 0


def dos_process_arg_str_accessors_test():
    p, proc, _ = _make_process()
    p.set_arg_str_ptr(0x1234)
    assert proc.pr_Arguments.aptr == 0x1234
    assert p.get_arg_str_ptr() == 0x1234


def dos_process_inherited_accessors_test():
    # the dir/var/cli accessors are no longer duplicated in ProcessBase
    for name in (
        "get_current_dir",
        "set_current_dir",
        "get_home_dir",
        "set_home_dir",
        "get_local_vars",
        "get_cli_struct",
    ):
        assert getattr(ProcessBase, name) is getattr(DosProcess, name)


# ----- BinProcess (single binary + uCLI) -----


class _FakeFH:
    def __init__(self, b_addr):
        self.b_addr = b_addr
        self.buf = None

    def setbuf(self, data):
        self.buf = data


class _FakeLock:
    def __init__(self, b_addr, ami_path, mem_addr):
        self.b_addr = b_addr
        self.ami_path = ami_path
        self.mem = SimpleNamespace(addr=mem_addr)


class _FakeLockMgr:
    def __init__(self):
        self.released = []

    def create_lock(self, lock, name, exclusive):
        return _FakeLock(0x40, name, 0x7000)

    def release_lock(self, lock):
        self.released.append(lock)

    def get_by_b_addr(self, b_addr):
        return None


class _FakeSeglist:
    def __init__(self, start):
        self.start = start

    def get_segment(self):
        return SimpleNamespace(get_addr=lambda: self.start)

    def __iter__(self):
        return iter([SimpleNamespace(name="seg")])


class _FakeSegLoader:
    def __init__(self, start):
        self.start = start
        self.unloaded = []

    def load_ami_seglist(self, path, lock):
        return 0x5000

    def get_info(self, b_addr):
        return SimpleNamespace(seglist=_FakeSeglist(self.start))

    def unload_seglist(self, b_addr):
        self.unloaded.append(b_addr)


class _FakePathMgr:
    def ami_name_of_path(self, lock, path):
        return path.replace(":", "/").rsplit("/", 1)[-1]

    def ami_command_paths(self, lock, path):
        return [path]

    def ami_dir_of_path(self, lock, path):
        return "root:"

    def ami_volume_of_path(self, path):
        return "root"

    def get_cmd_paths(self):
        return ["C:", "work:"]


class _BinCtx:
    def __init__(self):
        self.machine = Machine()
        self.alloc = MemoryAlloc.for_machine(self.machine)
        self.mem = self.machine.get_mem()
        self.odg_base = 0x100
        self.lock_mgr = _FakeLockMgr()
        self.seg_loader = _FakeSegLoader(0x5010)
        self.path_mgr = _FakePathMgr()
        self.dos_lib = SimpleNamespace(
            lock_mgr=self.lock_mgr,
            handler_mgr=None,
            file_mgr=None,
        )
        self.input_fh = _FakeFH(0x10)
        self.output_fh = _FakeFH(0x20)

    def cleanup(self):
        assert self.alloc.is_all_free()
        self.machine.cleanup()


def dos_bin_process_regs_and_cli_test():
    ctx = _BinCtx()
    arg_str = "arg1 arg2\n"
    proc = BinProcess(
        ctx,
        "root:prog",
        arg_str,
        input_fh=ctx.input_fh,
        output_fh=ctx.output_fh,
        stack_size=4096,
    )
    try:
        assert proc.ok
        assert proc.get_program_name() == "prog"
        assert proc.is_native_shell() is False
        # the non-shell path never builds the shell packet / entry offset
        assert not hasattr(proc, "shell_start")
        assert not hasattr(proc, "shell_packet")

        # args: D0=len, A0=arg buffer, string visible to ReadItem()
        assert proc.arg_len == len(arg_str)
        assert ctx.mem.r_cstr(proc.arg_base) == arg_str
        assert proc.get_arg_str_ptr() == proc.arg_base
        assert ctx.input_fh.buf == arg_str

        regs = proc.get_sched_task().get_code().set_regs
        assert regs[REG_D0] == proc.arg_len
        assert regs[REG_A0] == proc.arg_base
        assert regs[REG_D2] == 4096
        assert regs[REG_A2] == ctx.odg_base
        assert regs[REG_A5] == ctx.odg_base
        assert regs[REG_A6] == ctx.odg_base
        assert REG_D1 not in regs

        # uCLI fields
        cli = CLIStruct(ctx.mem, proc.get_cli_struct())
        assert cli.cli_DefaultStack.val == 4096 // 4
        assert cli.cli_FailLevel.val == 10
        assert cli.cli_StandardInput.aptr == 0x10 << 2
        assert cli.cli_CurrentInput.aptr == 0x10 << 2
        assert cli.cli_StandardOutput.aptr == 0x20 << 2
        assert cli.cli_CurrentOutput.aptr == 0x20 << 2
        assert ctx.mem.r_bstr(cli.cli_Prompt.aptr) == "%N.%S> "
        assert ctx.mem.r_bstr(cli.cli_SetName.aptr) == "SYS:"
        assert ctx.mem.r_bstr(cli.cli_CommandName.aptr) == "prog"
        # the command path chain is built (C: skipped, work: linked)
        assert cli.cli_CommandDir.aptr != 0

        # the Process struct points at the same CLI and streams
        assert proc.proc.pr_CLI.aptr == proc.get_cli_struct()
        assert proc.proc.pr_CIS.aptr == 0x10 << 2
        assert proc.proc.pr_COS.aptr == 0x20 << 2
    finally:
        proc.free()
        ctx.cleanup()


def dos_bin_process_free_test():
    ctx = _BinCtx()
    proc = BinProcess(
        ctx,
        "root:prog",
        "x\n",
        input_fh=ctx.input_fh,
        output_fh=ctx.output_fh,
    )
    proc.free()
    # free() released the home lock and unloaded the binary
    assert ctx.seg_loader.unloaded == [0x5000]
    assert ctx.lock_mgr.released
    # all allocated memory is back (cleanup asserts is_all_free)
    ctx.cleanup()
