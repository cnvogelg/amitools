import pytest

from amitools.vamos.machine import Machine, Runtime, Code, REG_D0
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.cmdcore import CommandManager
from amitools.vamos.loader import SegmentLoader
from helper import HostFileOpener

# a minimal Python command file with a shebang
PY_CMD = b"#!/usr/bin/env python3\ndef main(ctx, arg_line, prog_name):\n    return 7\n"


class Context:
    def __init__(self):
        self.mach = Machine()
        self.cpu = self.mach.get_cpu()
        self.mem = self.mach.get_mem()
        self.stack = self.mach.get_scratch_top()
        self.alloc = MemoryAlloc(self.mem, label_mgr=self.mach.get_label_mgr())
        self.rt = Runtime(self.mach)
        self.mgr = CommandManager(self.mach, self.alloc, self.rt.run)

    def make_loader(self, with_manager=True):
        if with_manager:
            return SegmentLoader(self.alloc, command_manager=self.mgr)
        return SegmentLoader(self.alloc)

    def run_stub(self, seglist):
        code = Code(seglist.get_start_pc(), self.stack)
        return self.rt.start(code)

    def cleanup(self):
        self.mgr.shutdown()
        self.mach.cleanup()


@pytest.fixture
def ctx():
    return Context()


@pytest.fixture
def py_file(tmp_path):
    p = tmp_path / "hello.py"
    p.write_bytes(PY_CMD)
    return str(p)


# ----- int_load_seglist -----


def command_segload_int_py_test(ctx, py_file):
    loader = ctx.make_loader()
    with open(py_file, "rb") as f:
        info = loader.int_load_seglist(f, name="cmds/hello.py")
    assert info is not None
    # the bin image is dropped; the command owns the stub
    assert info.bin_img is None
    assert info.name == "cmds/hello.py"
    assert info.command is not None
    assert info.command.name == "hello"
    assert info.seglist.get_baddr() > 0
    # the stub runs the command and returns its exit code
    rs = ctx.run_stub(info.seglist)
    assert rs.exit
    assert ctx.cpu.r_reg(REG_D0) == 7
    ctx.mgr.free_stub(info.command)
    assert ctx.alloc.is_all_free()
    ctx.cleanup()


def command_segload_int_py_lazy_test(ctx, py_file):
    """the command module is loaded lazily on first execution"""
    loader = ctx.make_loader()
    with open(py_file, "rb") as f:
        info = loader.int_load_seglist(f, name="cmds/hello.py")
    assert not info.command.has_main()
    ctx.run_stub(info.seglist)
    assert info.command.has_main()
    ctx.mgr.free_stub(info.command)
    ctx.cleanup()


def command_segload_int_py_name_test(ctx, py_file):
    loader = ctx.make_loader()
    with open(py_file, "rb") as f:
        info = loader.int_load_seglist(f, name="cmds/greet.py")
    assert info.command.name == "greet"
    ctx.mgr.free_stub(info.command)
    ctx.cleanup()


def command_segload_int_py_no_manager_test(ctx, py_file):
    """without a command manager a Python file cannot be loaded"""
    loader = ctx.make_loader(with_manager=False)
    with open(py_file, "rb") as f:
        info = loader.int_load_seglist(f, name="cmds/hello.py")
    assert info is None
    assert ctx.alloc.is_all_free()
    ctx.cleanup()


def command_segload_int_hunk_still_works_test(ctx, buildlibnix):
    """a normal hunk binary is still handled by the regular path"""
    loader = ctx.make_loader()
    lib_file = buildlibnix.make_lib("testnix")
    with open(lib_file, "rb") as f:
        info = loader.int_load_seglist(f, name=lib_file)
    assert info is not None
    assert info.command is None
    assert info.bin_img is not None
    info.seglist.free()
    assert ctx.alloc.is_all_free()
    ctx.cleanup()


# ----- load_seglist / unload_seglist -----


def command_segload_load_unload_test(ctx, py_file):
    loader = ctx.make_loader()
    with open(py_file, "rb") as f:
        baddr = loader.load_seglist(f, name="cmds/hello.py")
    assert baddr > 0
    info = loader.get_info(baddr)
    assert info.command is not None
    tid = info.command.tid
    assert tid is not None
    rs = ctx.run_stub(info.seglist)
    assert rs.exit
    assert ctx.cpu.r_reg(REG_D0) == 7
    # unload frees the stub and trap via the command manager
    assert loader.unload_seglist(baddr)
    assert info.command.seglist is None
    assert info.command.tid is None
    assert ctx.mgr.stubs == []
    assert ctx.alloc.is_all_free()
    ctx.cleanup()


def command_segload_shutdown_test(ctx, py_file):
    """shutdown frees an orphaned Python command stub"""
    loader = ctx.make_loader()
    with open(py_file, "rb") as f:
        baddr = loader.load_seglist(f, name="cmds/hello.py")
    assert baddr > 0
    info = loader.get_info(baddr)
    cmd = info.command
    assert loader.shutdown() == 1
    assert cmd.seglist is None
    assert cmd.tid is None
    assert ctx.alloc.is_all_free()
    ctx.cleanup()


def command_segload_ami_test(ctx, py_file):
    """a Python command loads through the Amiga path opener too"""
    loader = ctx.make_loader()
    opener = HostFileOpener({"cmds/hello.py": py_file})
    loader.set_file_opener(opener)
    baddr = loader.load_ami_seglist("cmds/hello.py")
    assert baddr > 0
    info = loader.get_info(baddr)
    assert info.command.name == "hello"
    assert info.ami_file == "cmds/hello.py"
    rs = ctx.run_stub(info.seglist)
    assert rs.exit
    assert ctx.cpu.r_reg(REG_D0) == 7
    assert loader.unload_seglist(baddr)
    assert ctx.alloc.is_all_free()
    ctx.cleanup()


# ----- command manager accessors -----


def command_segload_manager_accessor_test(ctx):
    loader = ctx.make_loader(with_manager=False)
    assert loader.get_command_manager() is None
    loader.set_command_manager(ctx.mgr)
    assert loader.get_command_manager() is ctx.mgr
    ctx.cleanup()
