"""dos.library stdio/error output functions (Step 18)."""

from types import SimpleNamespace

from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import ProcessStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1, REG_D2, REG_D3, REG_D4

from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    ERROR_NOT_IMPLEMENTED,
)

PROC_ADDR = 0x2000
TEXT_ADDR = 0x400


class _File:
    def __init__(self):
        self.data = []

    def write(self, data):
        self.data.append(bytes(data))


class _FileMgr:
    def __init__(self, handles):
        self.handles = handles

    def get_by_b_addr(self, b_addr, for_writing=None):
        if b_addr not in self.handles:
            raise ValueError("invalid handle %s" % b_addr)
        return self.handles[b_addr]


def _long(mem, cpu, reg, value):
    cpu.w_reg(reg, value)
    return LONG(cpu=cpu, reg=reg, mem=mem)


def _cstr(mem, cpu, reg, text):
    cpu.w_reg(reg, TEXT_ADDR)
    mem.w_cstr(TEXT_ADDR, text)
    return CSTR(cpu=cpu, reg=reg, mem=mem)


def _make_lib():
    mem = MockMemory()
    cpu = MockCPU()
    proc = ProcessStruct(mem, PROC_ADDR)
    proc.pr_CES.bptr = 0
    proc.pr_COS.bptr = 0
    lib = DosLibrary()
    lib.file_mgr = _FileMgr({20: _File(), 21: _File()})
    ctx = SimpleNamespace(
        mem=mem,
        cpu=cpu,
        process=SimpleNamespace(get_ami_process=lambda: proc),
    )
    return lib, ctx, mem, cpu, proc


def lib_dos_stdio_error_output_test():
    lib, ctx, mem, cpu, proc = _make_lib()
    proc.pr_COS.bptr = 21
    assert lib.ErrorOutput(ctx) == 21
    proc.pr_CES.bptr = 20
    assert lib.ErrorOutput(ctx) == 20

    old = lib.SelectError(ctx, _long(mem, cpu, REG_D1, 21))
    assert old == 20
    assert proc.pr_CES.bptr == 21
    old = lib.SelectError(ctx, _long(mem, cpu, REG_D1, 0))
    assert old == 21
    assert proc.pr_CES.bptr == 0


def lib_dos_stdio_put_err_str_test():
    lib, ctx, mem, cpu, proc = _make_lib()
    lib.MAX_SHOW_DATA = 16
    proc.pr_COS.bptr = 21

    text = _cstr(mem, cpu, REG_D1, "error text")
    assert lib.PutErrStr(ctx, text) == 0
    assert lib.file_mgr.handles[21].data == [b"error text"]

    # NULL string is ignored
    cpu.w_reg(REG_D1, 0)
    assert lib.PutErrStr(ctx, CSTR(cpu=cpu, reg=REG_D1, mem=mem)) == 0
    assert lib.file_mgr.handles[21].data == [b"error text"]

    # invalid handle is logged but does not crash
    proc.pr_COS.bptr = 99
    text = _cstr(mem, cpu, REG_D1, "ignored")
    assert lib.PutErrStr(ctx, text) == 0
    assert lib.file_mgr.handles[21].data == [b"error text"]


def lib_dos_stdio_error_report_test():
    lib, ctx, mem, cpu, _proc = _make_lib()
    assert (
        lib.ErrorReport(
            ctx,
            _long(mem, cpu, REG_D1, 205),
            _long(mem, cpu, REG_D2, 0),
            _long(mem, cpu, REG_D3, 1),
            _long(mem, cpu, REG_D4, 0),
        )
        == DOSFALSE
    )
    assert lib.io_err == ERROR_NOT_IMPLEMENTED
