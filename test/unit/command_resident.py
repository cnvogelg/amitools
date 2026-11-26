"""Unit tests for registering Python commands as DOS resident segments."""

from types import SimpleNamespace

from amitools.vamos.cmdcore import CommandManager, ResidentCommands
from amitools.vamos.lib.dos.Helper import alloc_mem, free_mem
from amitools.vamos.lib.dos.Segments import add_segment, find_segment
from amitools.vamos.libstructs import DosInfoStruct
from amitools.vamos.machine import Machine, Runtime
from amitools.vamos.mem import MemoryAlloc

# a minimal Python command file with a shebang
PY_CMD = b"#!/usr/bin/env python3\ndef main(ctx, arg_line, prog_name):\n    return 7\n"

INFO_ADDR = 0x100


class FakeDos:
    """the dos.library bits ResidentCommands uses (real segment structs)"""

    def __init__(self, mem, alloc):
        self.mem = mem
        self.alloc = alloc
        self.mem_allocs = {}
        self.seg_lists = {}
        self.resident = []
        self.dos_info_struct = DosInfoStruct(mem, INFO_ADDR)

    def _alloc_mem(self, name, size):
        return alloc_mem(self, name, size)

    def _free_mem(self, addr):
        return free_mem(self, addr)

    def AddSegment(self, ctx, name_ptr, seglist, system):
        return add_segment(self, ctx, name_ptr, seglist, system)


class Context:
    def __init__(self):
        self.mach = Machine()
        self.mem = self.mach.get_mem()
        self.alloc = MemoryAlloc(self.mem, label_mgr=self.mach.get_label_mgr())
        self.rt = Runtime(self.mach)
        self.mgr = CommandManager(self.mach, self.alloc, self.rt.run)
        self.dos = FakeDos(self.mem, self.alloc)
        self.dos_ctx = SimpleNamespace(mem=self.mem)
        self.resident = ResidentCommands(self.mgr)
        self.resident.setup(self.dos, self.dos_ctx)

    def find(self, name):
        addr = self.dos._alloc_mem("Name", len(name) + 1)
        self.mem.w_cstr(addr, name)
        try:
            return find_segment(self.dos, self.dos_ctx, addr, 0, 0)
        finally:
            self.dos._free_mem(addr)

    def cleanup(self):
        self.resident.shutdown()
        self.mgr.shutdown()
        self.mach.cleanup()


def command_resident_add_source_test():
    ctx = Context()
    cmd = ctx.resident.add_source("hello", PY_CMD)
    assert cmd.name == "hello"
    # the command is booked in the resident list and the seglist table
    assert len(ctx.dos.resident) == 1
    seg_addr = ctx.dos.resident[0]
    assert ctx.resident.entries == [("hello", seg_addr, cmd.seglist.get_baddr())]
    assert ctx.dos.seg_lists[cmd.seglist.get_baddr()] == "hello"
    # FindSegment(system=0) finds a user resident command
    assert ctx.find("hello") == seg_addr
    ctx.cleanup()
    assert ctx.alloc.is_all_free()


def command_resident_add_source_no_setup_test():
    """registering before setup() fails cleanly"""
    ctx = Context()
    resident = ResidentCommands(ctx.mgr)
    try:
        resident.add_source("hello", PY_CMD)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
    # nothing was allocated
    assert ctx.alloc.is_all_free()
    ctx.cleanup()


def command_resident_shutdown_test():
    ctx = Context()
    ctx.resident.add_source("one", PY_CMD)
    ctx.resident.add_source("two", PY_CMD)
    assert len(ctx.dos.resident) == 2
    assert len(ctx.dos.seg_lists) == 2
    ctx.resident.shutdown()
    # the resident nodes and seglist bookings are gone; the stubs are freed
    # separately by the command manager
    assert ctx.resident.entries == []
    assert ctx.dos.resident == []
    assert ctx.dos.seg_lists == {}
    assert len(ctx.mgr.stubs) == 2
    ctx.mgr.shutdown()
    assert ctx.mgr.stubs == []
    assert ctx.alloc.is_all_free()
    # both shutdowns are idempotent
    ctx.resident.shutdown()
    ctx.mgr.shutdown()
    assert ctx.alloc.is_all_free()
    ctx.cleanup()


def command_resident_add_dir_test(tmp_path):
    ctx = Context()
    (tmp_path / "hello.py").write_bytes(PY_CMD)
    (tmp_path / "world.py").write_bytes(PY_CMD)
    # these must be ignored
    (tmp_path / "_private.py").write_bytes(PY_CMD)
    (tmp_path / "readme.txt").write_text("nope")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.py").write_bytes(PY_CMD)

    count = ctx.resident.add_dir(str(tmp_path))
    assert count == 2
    assert ctx.find("hello") != 0
    assert ctx.find("world") != 0
    assert ctx.find("_private") == 0
    assert ctx.find("nested") == 0
    ctx.cleanup()
    assert ctx.alloc.is_all_free()


def command_resident_add_dir_missing_test():
    """a missing directory is reported and registers nothing"""
    ctx = Context()
    assert ctx.resident.add_dir("/no/such/dir") == 0
    assert ctx.resident.entries == []
    ctx.cleanup()
    assert ctx.alloc.is_all_free()
