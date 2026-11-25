"""``MicroCLI``: the minimal CLIStruct built for a single binary.

Step 5 of the shell refactor extracted the uCLI ("micro CLI") construction
from ``Process`` into ``lib/dos/ucli.py``.  These tests pin down the field set
and the command-path chain the helper is responsible for, independently of a
full vamos context.
"""

from types import SimpleNamespace

from amitools.vamos.lib.dos.ucli import MicroCLI
from amitools.vamos.libstructs import CLIStruct, PathStruct
from amitools.vamos.machine import Machine
from amitools.vamos.mem import MemoryAlloc


class _FH:
    def __init__(self, b_addr):
        self.b_addr = b_addr


class _Lock:
    def __init__(self, mem_addr):
        self.mem = SimpleNamespace(addr=mem_addr)


class _LockMgr:
    def __init__(self, fail=()):
        self.fail = set(fail)
        self.released = []

    def create_lock(self, lock, name, exclusive):
        if name in self.fail:
            return None
        return _Lock(0x7000)

    def release_lock(self, lock):
        self.released.append(lock)


class _PathMgr:
    def __init__(self, paths):
        self.paths = paths

    def get_cmd_paths(self):
        return self.paths


class _Ctx:
    def __init__(self, paths=("C:", "work:"), fail=()):
        self.machine = Machine()
        self.alloc = MemoryAlloc.for_machine(self.machine)
        self.mem = self.machine.get_mem()
        self.lock_mgr = _LockMgr(fail)
        self.path_mgr = _PathMgr(list(paths))
        self.dos_lib = SimpleNamespace(lock_mgr=self.lock_mgr)

    def cleanup(self):
        assert self.alloc.is_all_free()
        self.machine.cleanup()


def lib_dos_ucli_fields_test():
    ctx = _Ctx()
    ucli = MicroCLI(ctx, _FH(0x10), _FH(0x20), "prog", 4096)
    try:
        assert ucli.addr == ucli.cli.addr
        cli = CLIStruct(ctx.mem, ucli.addr)
        assert cli.cli_DefaultStack.val == 4096 // 4
        assert cli.cli_FailLevel.val == 10
        assert cli.cli_StandardInput.aptr == 0x10 << 2
        assert cli.cli_CurrentInput.aptr == 0x10 << 2
        assert cli.cli_StandardOutput.aptr == 0x20 << 2
        assert cli.cli_CurrentOutput.aptr == 0x20 << 2
        assert ctx.mem.r_bstr(cli.cli_Prompt.aptr) == "%N.%S> "
        assert ctx.mem.r_bstr(cli.cli_SetName.aptr) == "SYS:"
        assert ctx.mem.r_bstr(cli.cli_CommandName.aptr) == "prog"
        # shell-only state is left at its zero default
        assert cli.cli_Interactive.val == 0
        assert cli.cli_Background.val == 0
        assert cli.cli_Module.aptr == 0
    finally:
        ucli.free()
        ctx.cleanup()


def lib_dos_ucli_command_path_test():
    ctx = _Ctx(paths=["C:", "work:", "sys:"])
    ucli = MicroCLI(ctx, _FH(0x10), _FH(0x20), "prog", 4096)
    try:
        cli = CLIStruct(ctx.mem, ucli.addr)
        # C: is skipped, work: and sys: are linked as a Path chain
        assert len(ucli.paths) == 2
        head = PathStruct(ctx.mem, cli.cli_CommandDir.aptr)
        tail = PathStruct(ctx.mem, head.path_Next.aptr)
        assert head.path_Lock.aptr == 0x7000
        assert tail.path_Lock.aptr == 0x7000
        assert tail.path_Next.aptr == 0
    finally:
        ucli.free()
        assert len(ctx.lock_mgr.released) == 2
        ctx.cleanup()


def lib_dos_ucli_missing_path_test():
    # a command path that can't be locked is skipped, not fatal
    ctx = _Ctx(paths=["C:", "work:", "nope:"], fail=["nope:"])
    ucli = MicroCLI(ctx, _FH(0x10), _FH(0x20), "prog", 4096)
    try:
        assert len(ucli.paths) == 1
    finally:
        ucli.free()
        ctx.cleanup()
