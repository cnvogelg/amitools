"""dos.library segment functions (Step 18)."""

from types import SimpleNamespace

from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import DosInfoStruct, SegmentStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_A1, REG_D1

from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_REQUIRED_ARG_MISSING,
)

INFO_ADDR = 0x100
SEG1_ADDR = 0x200
SEG2_ADDR = 0x300


def _long(mem, cpu, reg, value):
    cpu.w_reg(reg, value)
    return LONG(cpu=cpu, reg=reg, mem=mem)


def _cstr(mem, cpu, reg, text, base=0x400):
    cpu.w_reg(reg, base)
    mem.w_cstr(base, text)
    return CSTR(cpu=cpu, reg=reg, mem=mem)


def _make_lib():
    mem = MockMemory()
    cpu = MockCPU()
    dos_info = DosInfoStruct(mem, INFO_ADDR)
    seg1 = SegmentStruct(mem, SEG1_ADDR)
    seg2 = SegmentStruct(mem, SEG2_ADDR)
    seg1.seg_Next.aptr = SEG2_ADDR
    seg2.seg_Next.aptr = 0
    dos_info.di_NetHand.aptr = SEG1_ADDR
    lib = DosLibrary()
    lib.dos_info_struct = dos_info
    lib.resident = [SEG1_ADDR, SEG2_ADDR]
    ctx = SimpleNamespace(mem=mem, cpu=cpu, process=None)
    return lib, ctx, mem, cpu, dos_info, seg1, seg2


def lib_dos_segments_rem_segment_test():
    lib, ctx, mem, cpu, dos_info, seg1, seg2 = _make_lib()
    freed = []
    lib._free_mem = freed.append

    seg = _long(mem, cpu, REG_D1, SEG2_ADDR)
    assert lib.RemSegment(ctx, seg) == DOSTRUE
    assert lib.io_err == 0
    assert dos_info.di_NetHand.aptr == SEG1_ADDR
    assert seg1.seg_Next.aptr == 0
    assert freed == [SEG2_ADDR]
    assert lib.resident == [SEG1_ADDR]


def lib_dos_segments_rem_segment_head_test():
    lib, ctx, mem, cpu, dos_info, seg1, seg2 = _make_lib()
    freed = []
    lib._free_mem = freed.append

    seg = _long(mem, cpu, REG_D1, SEG1_ADDR)
    assert lib.RemSegment(ctx, seg) == DOSTRUE
    assert dos_info.di_NetHand.aptr == SEG2_ADDR
    assert freed == [SEG1_ADDR]


def lib_dos_segments_rem_segment_missing_test():
    lib, ctx, mem, cpu, dos_info, _seg1, _seg2 = _make_lib()
    freed = []
    lib._free_mem = freed.append

    seg = _long(mem, cpu, REG_D1, 0x700)
    assert lib.RemSegment(ctx, seg) == DOSFALSE
    assert lib.io_err == ERROR_OBJECT_NOT_FOUND
    assert freed == []

    seg = _long(mem, cpu, REG_D1, 0)
    assert lib.RemSegment(ctx, seg) == DOSFALSE
    assert lib.io_err == ERROR_REQUIRED_ARG_MISSING


def lib_dos_segments_new_load_seg_test():
    mem = MockMemory()
    cpu = MockCPU()
    lib = DosLibrary()
    lib.get_current_dir = lambda ctx: None
    calls = []

    def load(ctx, name, lock):
        calls.append((name, lock))
        return 0x1234

    lib._load_seg_list = load
    ctx = SimpleNamespace(mem=mem, cpu=cpu, process=None)

    name = _cstr(mem, cpu, REG_D1, "work:prog")
    assert lib.NewLoadSeg(ctx, name, None) == 0x1234
    assert calls == [("work:prog", None)]

    # a NULL name does not load anything
    cpu.w_reg(REG_D1, 0)
    assert lib.NewLoadSeg(ctx, CSTR(cpu=cpu, reg=REG_D1, mem=mem), None) == 0
    assert calls == [("work:prog", None)]


def lib_dos_segments_unload_test():
    mem = MockMemory()
    cpu = MockCPU()
    lib = DosLibrary()
    calls = []
    lib._unload_seg_list = lambda ctx, b_addr: calls.append(b_addr)
    ctx = SimpleNamespace(mem=mem, cpu=cpu, process=None)

    seglist = _long(mem, cpu, REG_D1, 0x2222)
    freefunc = _long(mem, cpu, REG_A1, 0x3333)
    assert lib.InternalUnLoadSeg(ctx, seglist, freefunc) is None
    assert calls == [0x2222]

    seglist = _long(mem, cpu, REG_D1, 0)
    freefunc = _long(mem, cpu, REG_A1, 0)
    assert lib.InternalUnLoadSeg(ctx, seglist, freefunc) is None
    assert calls == [0x2222, 0]
