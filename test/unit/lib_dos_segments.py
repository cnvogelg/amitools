"""dos.library segment functions (Step 18)."""

from types import SimpleNamespace

from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    DOSTRUE_S,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_OBJECT_WRONG_TYPE,
    ERROR_REQUIRED_ARG_MISSING,
)
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import DosInfoStruct, SegmentStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_A1, REG_D1

INFO_ADDR = 0x100
SEG1_ADDR = 0x200
SEG2_ADDR = 0x300
NAME_ADDR = 0x400


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
    lib, ctx, mem, cpu, dos_info, seg1, _seg2 = _make_lib()
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
    lib, ctx, mem, cpu, dos_info, _seg1, _seg2 = _make_lib()
    freed = []
    lib._free_mem = freed.append

    seg = _long(mem, cpu, REG_D1, SEG1_ADDR)
    assert lib.RemSegment(ctx, seg) == DOSTRUE
    assert dos_info.di_NetHand.aptr == SEG2_ADDR
    assert freed == [SEG1_ADDR]


def lib_dos_segments_rem_segment_missing_test():
    lib, ctx, mem, cpu, _dos_info, _seg1, _seg2 = _make_lib()
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


class _FakeSegLoader:
    """minimal ctx.seg_loader used by the segment booking helpers"""

    def __init__(self, b_addr=0x8000):
        self.b_addr = b_addr
        self.loaded = []
        self.unloaded = []
        self.info = SimpleNamespace(has_overlay=lambda: False)

    def load_seglist(self, fobj, name=None):
        self.loaded.append(name)
        return self.b_addr

    def load_ami_seglist(self, name, lock=None):
        self.loaded.append(name)
        return self.b_addr

    def unload_seglist(self, b_addr):
        self.unloaded.append(b_addr)
        return True

    def get_info(self, b_addr):
        return self.info


def _add_resident(lib, ctx, mem, name, seglist, system, addr):
    """book a resident command through AddSegment at a fixed address"""
    mem.w_cstr(NAME_ADDR, name)
    lib._alloc_mem = lambda label, size: addr
    assert lib.AddSegment(ctx, NAME_ADDR, seglist, system) == DOSTRUE_S
    return addr


def lib_dos_segments_internal_load_seg_test():
    lib, ctx, _mem, _cpu, _dos_info, _seg1, _seg2 = _make_lib()
    lib.seg_lists = {}
    loader = _FakeSegLoader()
    ctx.seg_loader = loader

    # InternalLoadSeg is not implemented yet: it always fails with IoErr and
    # never hands a file to the segment loader.
    assert lib.InternalLoadSeg(ctx, 0x1234, 0, 0, 0) == 0
    assert lib.io_err == ERROR_OBJECT_WRONG_TYPE
    assert loader.loaded == []
    assert lib.seg_lists == {}


def lib_dos_segments_load_seg_test():
    lib, ctx, mem, _cpu, _dos_info, _seg1, _seg2 = _make_lib()
    lib.seg_lists = {}
    lib.get_current_dir = lambda ctx: None
    loader = _FakeSegLoader(b_addr=0x8000)
    ctx.seg_loader = loader

    # a successful load is booked for a later UnLoadSeg
    mem.w_cstr(NAME_ADDR, "work:prog")
    assert lib.LoadSeg(ctx, NAME_ADDR) == 0x8000
    assert loader.loaded == ["work:prog"]
    assert lib.seg_lists == {0x8000: "work:prog"}

    lib.UnLoadSeg(ctx, 0x8000)
    assert lib.seg_lists == {}
    assert loader.unloaded == [0x8000]


def lib_dos_segments_add_segment_test():
    lib, ctx, mem, _cpu, dos_info, _seg1, _seg2 = _make_lib()
    lib.seg_lists = {}
    allocs = []

    def alloc(name, size):
        allocs.append((name, size, 0x1000))
        return 0x1000

    lib._alloc_mem = alloc
    mem.w_cstr(NAME_ADDR, "mycmd")

    assert lib.AddSegment(ctx, NAME_ADDR, 0x2000, 1) == DOSTRUE_S

    seg_addr = dos_info.di_NetHand.aptr
    assert seg_addr == 0x1000
    segment = SegmentStruct(mem, seg_addr)
    assert segment.seg_Next.aptr == SEG1_ADDR
    assert segment.seg_UC.val == 1
    assert segment.seg_Seg.aptr == 0x2000 << 2
    name_addr = seg_addr + SegmentStruct.sdef.seg_Name.offset
    assert mem.r_bstr(name_addr) == "mycmd"
    assert lib.resident == [SEG1_ADDR, SEG2_ADDR, seg_addr]
    assert lib.seg_lists == {0x2000: "mycmd"}
    assert allocs == [("Segment", SegmentStruct.get_size() + len("mycmd") + 1, 0x1000)]


def lib_dos_segments_add_segment_system_test():
    lib, ctx, mem, _cpu, dos_info, _seg1, _seg2 = _make_lib()
    lib.seg_lists = {}

    # a system segment carries the -1 (DOSTRUE_S) use count bit pattern
    _add_resident(lib, ctx, mem, "sys.cmd", 0x2000, 0xFFFFFFFF, 0x1000)
    seg_addr = dos_info.di_NetHand.aptr
    assert SegmentStruct(mem, seg_addr).seg_UC.val == 0xFFFFFFFF

    # ... but seg_UC is unsigned, so FindSegment(system=True) cannot match it
    mem.w_cstr(NAME_ADDR, "sys.cmd")
    assert lib.FindSegment(ctx, NAME_ADDR, 0, 1) == 0


def lib_dos_segments_add_segment_duplicate_test():
    lib, ctx, mem, _cpu, _dos_info, _seg1, _seg2 = _make_lib()
    lib.seg_lists = {}

    _add_resident(lib, ctx, mem, "dup.cmd", 0x2000, 1, 0x1000)
    _add_resident(lib, ctx, mem, "dup.cmd", 0x2001, 1, 0x1100)

    # every distinct seglist is registered, even with the same name
    assert lib.seg_lists == {0x2000: "dup.cmd", 0x2001: "dup.cmd"}
    assert lib.resident == [SEG1_ADDR, SEG2_ADDR, 0x1000, 0x1100]

    # re-adding a known seglist keeps the first name
    _add_resident(lib, ctx, mem, "renamed", 0x2000, 1, 0x1200)
    assert lib.seg_lists == {0x2000: "dup.cmd", 0x2001: "dup.cmd"}
    assert lib.resident == [SEG1_ADDR, SEG2_ADDR, 0x1000, 0x1100, 0x1200]


def lib_dos_segments_find_segment_test():
    lib, ctx, mem, _cpu, dos_info, _seg1, _seg2 = _make_lib()
    lib.seg_lists = {}
    one = _add_resident(lib, ctx, mem, "cmd.one", 0x2000, 1, 0x1000)
    two = _add_resident(lib, ctx, mem, "cmd.two", 0x2001, 1, 0x1100)

    # the newest segment is at the head of the resident chain
    assert dos_info.di_NetHand.aptr == two

    mem.w_cstr(NAME_ADDR, "cmd.one")
    assert lib.FindSegment(ctx, NAME_ADDR, 0, 0) == one
    # lookup is case insensitive
    mem.w_cstr(NAME_ADDR, "CMD.TWO")
    assert lib.FindSegment(ctx, NAME_ADDR, 0, 0) == two
    # system=1 looks for a negative use count that AddSegment cannot create
    assert lib.FindSegment(ctx, NAME_ADDR, 0, 1) == 0


def lib_dos_segments_find_segment_start_test():
    lib, ctx, mem, _cpu, _dos_info, _seg1, _seg2 = _make_lib()
    lib.seg_lists = {}
    one = _add_resident(lib, ctx, mem, "cmd.one", 0x2000, 1, 0x1000)
    two = _add_resident(lib, ctx, mem, "cmd.two", 0x2001, 1, 0x1100)

    # start scanning after the given node
    mem.w_cstr(NAME_ADDR, "cmd.one")
    assert lib.FindSegment(ctx, NAME_ADDR, two, 0) == one
    # the node at start itself is skipped
    mem.w_cstr(NAME_ADDR, "cmd.two")
    assert lib.FindSegment(ctx, NAME_ADDR, two, 0) == 0


def lib_dos_segments_find_segment_not_found_test():
    lib, ctx, mem, _cpu, _dos_info, _seg1, _seg2 = _make_lib()
    lib.seg_lists = {}
    _add_resident(lib, ctx, mem, "cmd.one", 0x2000, 1, 0x1000)

    mem.w_cstr(NAME_ADDR, "no.such.cmd")
    assert lib.FindSegment(ctx, NAME_ADDR, 0, 0) == 0
    assert lib.FindSegment(ctx, NAME_ADDR, 0, 1) == 0
