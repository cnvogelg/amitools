import pytest

from amitools.vamos.machine import (
    Machine,
    Runtime,
    Code,
    REG_A0,
    REG_D0,
)
from amitools.vamos.machine.opcodes import op_rts, op_trap
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.cmdcore import CommandManager, PyCommand, RETURN_ERROR


class Context:
    def __init__(self):
        self.mach = Machine()
        self.cpu = self.mach.get_cpu()
        self.mem = self.mach.get_mem()
        self.stack = self.mach.get_scratch_top()
        self.alloc = MemoryAlloc(self.mem, label_mgr=self.mach.get_label_mgr())
        self.rt = Runtime(self.mach)
        self.mgr = CommandManager(self.mach, self.alloc, self.rt.run)

    def run_stub(self, cmd, set_regs=None):
        seglist = self.mgr.make_stub(cmd)
        # a DOS program is always entered with an argument line in A0/D0, so
        # default them to "no arguments" instead of relying on the reset state
        regs = {REG_A0: 0, REG_D0: 0}
        if set_regs:
            regs.update(set_regs)
        code = Code(seglist.get_start_pc(), self.stack, set_regs=regs)
        return self.rt.start(code)

    def cleanup(self):
        self.mgr.shutdown()
        self.mach.cleanup()


@pytest.fixture
def ctx():
    return Context()


def command_stub_return_value_test(ctx):
    """the value returned by main() ends up in D0"""
    cmd = ctx.mgr.make_command("test", main=lambda c, a, n: 42)
    rs = ctx.run_stub(cmd)
    assert rs.exit
    assert ctx.cpu.r_reg(REG_D0) == 42
    ctx.cleanup()


def command_stub_bytes_test(ctx):
    """the stub holds TRAP #tid followed by RTS"""
    cmd = ctx.mgr.make_command("test", main=lambda c, a, n: 0)
    seglist = ctx.mgr.make_stub(cmd)
    start = seglist.get_start_pc()
    assert ctx.mem.r16(start) == op_trap | cmd.tid
    assert ctx.mem.r16(start + 2) == op_rts
    # a DOS seglist BPTR points at block+4 and the entry is at block+8
    assert seglist.get_baddr() << 2 == start - 4
    ctx.cleanup()


def command_stub_prog_name_test(ctx):
    """main() receives the command name as prog_name"""
    seen = []
    cmd = ctx.mgr.make_command("hello", main=lambda c, a, n: seen.append((a, n)) or 0)
    ctx.run_stub(cmd)
    assert seen == [("", "hello")]
    ctx.cleanup()


def command_stub_arg_line_test(ctx):
    """the argument line is read from A0/D0"""
    arg = "hello world"
    arg_mem = ctx.alloc.alloc_cstr(arg)
    seen = []
    cmd = ctx.mgr.make_command("args", main=lambda c, a, n: seen.append(a) or 0)
    set_regs = {REG_A0: arg_mem.addr, REG_D0: len(arg)}
    ctx.run_stub(cmd, set_regs=set_regs)
    assert seen == [arg]
    ctx.cleanup()


def command_stub_no_arg_test(ctx):
    """an empty A0/D0 yields an empty argument line"""
    seen = []
    cmd = ctx.mgr.make_command("args", main=lambda c, a, n: seen.append(a) or 0)
    set_regs = {REG_A0: 0, REG_D0: 0}
    ctx.run_stub(cmd, set_regs=set_regs)
    assert seen == [""]
    ctx.cleanup()


def command_stub_exit_code_mask_test(ctx):
    """the exit code is masked to the DOS 0..255 range"""
    cmd = ctx.mgr.make_command("neg", main=lambda c, a, n: -1)
    ctx.run_stub(cmd)
    assert ctx.cpu.r_reg(REG_D0) == 0xFF
    ctx.cleanup()


def command_stub_exception_test(ctx):
    """an exception inside main() yields a non-zero exit code"""

    def boom(c, a, n):
        raise ValueError("boom")

    cmd = ctx.mgr.make_command("boom", main=boom)
    rs = ctx.run_stub(cmd)
    assert rs.exit
    assert ctx.cpu.r_reg(REG_D0) == RETURN_ERROR
    ctx.cleanup()


def command_stub_free_test(ctx):
    """shutdown frees the stub seglist and the trap"""
    cmd = ctx.mgr.make_command("test", main=lambda c, a, n: 0)
    ctx.run_stub(cmd)
    assert cmd.tid is not None
    assert not ctx.alloc.is_all_free()
    ctx.mgr.shutdown()
    assert cmd.tid is None
    assert cmd.seglist is None
    assert ctx.mgr.stubs == []
    assert ctx.alloc.is_all_free()
    ctx.mach.cleanup()


def command_stub_free_explicit_test(ctx):
    """free_stub frees a single command's stub and trap"""
    cmd = ctx.mgr.make_command("test", main=lambda c, a, n: 0)
    ctx.mgr.make_stub(cmd)
    tid = cmd.tid
    assert cmd.seglist is not None
    ctx.mgr.free_stub(cmd)
    assert cmd.seglist is None
    assert cmd.tid is None
    assert ctx.mgr.stubs == []
    # trap was released (real Traps returns None, mock raises)
    try:
        assert ctx.mach.get_traps().get_func(tid) is None
    except KeyError:
        pass
    ctx.cleanup()


def command_stub_double_stub_test(ctx):
    """a command cannot get two stubs"""
    cmd = ctx.mgr.make_command("test", main=lambda c, a, n: 0)
    ctx.mgr.make_stub(cmd)
    with pytest.raises(ValueError):
        ctx.mgr.make_stub(cmd)
    ctx.cleanup()


def command_stub_nested_run_test(ctx):
    """a command may issue a nested m68k run through the runner"""

    def main(c, a, n):
        # run a small piece of code that just returns
        rs = c.runner(Code(0x1000, ctx.stack))
        return 1 if rs.exit else 0

    # place an RTS at the ram begin
    ctx.mem.w16(0x1000, op_rts)
    cmd = ctx.mgr.make_command("nested", main=main)
    rs = ctx.run_stub(cmd)
    assert rs.exit
    assert ctx.cpu.r_reg(REG_D0) == 1
    ctx.cleanup()


def command_stub_pycommand_run_test(ctx):
    """PyCommand.run masks the return value and defaults None to 0"""
    cmd = PyCommand("x", main=lambda c, a, n: 256)
    assert cmd.run(None, "") == 0
    cmd = PyCommand("x", main=lambda c, a, n: None)
    assert cmd.run(None, "") == 0
