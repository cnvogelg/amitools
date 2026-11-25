"""dos.library AllocDosObject/FreeDosObject (the DOS_CLI string buffers)."""

from types import SimpleNamespace

from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import CLIStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.mem import MemoryAlloc

DOS_CLI = 4


def _make_lib(mem):
    lib = DosLibrary()
    lib.alloc = MemoryAlloc(mem)
    lib.dos_objs = {}
    return lib


def _make_ctx(mem, cpu, lib):
    return SimpleNamespace(mem=mem, cpu=cpu, alloc=lib.alloc)


def lib_dos_alloc_dos_object_cli_test():
    mem = MockMemory()
    cpu = MockCPU()
    lib = _make_lib(mem)
    ctx = _make_ctx(mem, cpu, lib)

    ptr = lib.AllocDosObject(ctx, DOS_CLI, 0)
    assert ptr != 0
    cli = CLIStruct(mem, ptr)

    # the four string fields must point at real (non-NULL) buffers: DOS and
    # programs such as RexxMast write through them (SetPrompt, ...)
    for field in ("cli_Prompt", "cli_CommandName", "cli_CommandFile", "cli_SetName"):
        assert getattr(cli, field).aptr != 0, field
    # they are distinct buffers
    addrs = {
        cli.cli_Prompt.aptr,
        cli.cli_CommandName.aptr,
        cli.cli_CommandFile.aptr,
        cli.cli_SetName.aptr,
    }
    assert len(addrs) == 4

    # sane defaults
    assert cli.cli_FailLevel.val == 10
    assert cli.cli_DefaultStack.val == 4000 // 4
    assert mem.r_bstr(cli.cli_SetName.aptr) == "SYS:"
    assert mem.r_bstr(cli.cli_CommandName.aptr) == ""
    assert mem.r_bstr(cli.cli_CommandFile.aptr) == ""
    assert mem.r_bstr(cli.cli_Prompt.aptr) == "%N.%S> "

    # a second CLI is independent (fresh buffers)
    ptr2 = lib.AllocDosObject(ctx, DOS_CLI, 0)
    assert ptr2 != 0 and ptr2 != ptr
    cli2 = CLIStruct(mem, ptr2)
    assert cli2.cli_Prompt.aptr not in addrs

    # freeing releases the struct and its four buffers
    lib.FreeDosObject(ctx, DOS_CLI, ptr)
    lib.FreeDosObject(ctx, DOS_CLI, ptr2)
    assert lib.dos_objs == {}
    assert lib.alloc.is_all_free()


def lib_dos_free_dos_object_cli_unknown_test():
    # freeing an unknown pointer is reported but does not raise
    mem = MockMemory()
    cpu = MockCPU()
    lib = _make_lib(mem)
    ctx = _make_ctx(mem, cpu, lib)

    lib.FreeDosObject(ctx, DOS_CLI, 0x1234)
    assert lib.dos_objs == {}
