import ctypes
import sys
from types import SimpleNamespace

import pytest

from amitools.vamos.label import LabelManager
from amitools.vamos.lib.GraphicsLibrary import GraphicsLibrary, RPBatch
from amitools.vamos.lib.graphics import BitMapStruct, RastPortStruct
from amitools.vamos.lib.intuition import TextFontStruct
from amitools.vamos.machine import (
    Machine,
    Runtime,
    Code,
    REG_A0,
    REG_A1,
    REG_D0,
    REG_D1,
    REG_D2,
    REG_D3,
)
from amitools.vamos.machine.mock import MockMemory, MockCPU
from amitools.vamos.mem import MemoryAlloc


class Context:
    def __init__(self, labels, machine=None):
        self.machine = machine
        self.mem = machine.get_mem() if machine else MockMemory()
        self.cpu = machine.get_cpu() if machine else MockCPU()
        self.labels = LabelManager() if labels else None
        self.alloc = MemoryAlloc(
            self.mem,
            addr=machine.get_ram_begin() if machine else 0,
            label_mgr=self.labels,
        )
        self.font = TextFontStruct.alloc(self.alloc)
        self.font.tf_YSize.val = self.font.tf_XSize.val = 8
        self.font.tf_Baseline.val = 6
        self.font.tf_Flags.val = 0x21
        self.font.tf_Accessors.val = 7
        self.font.tf_CharSpace.val = 0x123456
        self.block = self.alloc.alloc_memory(108, label="guarded RastPort")
        self.raster = RastPortStruct(self.mem, self.block.addr + 4)
        self.graphics = GraphicsLibrary()
        self.graphics.alloc = self.alloc
        self.graphics.topaz_font = self.font.get_addr()

    def initialize(self):
        self.cpu.w_reg(REG_A1, self.raster.get_addr())
        self.graphics.InitRastPort(self)

    def check_defaults(self):
        rp = self.raster
        assert rp.get_size() == 100
        for field in (
            "Layer",
            "BitMap",
            "AreaPtrn",
            "TmpRas",
            "AreaInfo",
            "GelsInfo",
            "RP_User",
        ):
            assert rp.get(field).val == 0
        for field in (
            "BgPen",
            "AreaPtSz",
            "linpatcnt",
            "dummy",
            "Flags",
            "cp_x",
            "cp_y",
            "PenWidth",
            "PenHeight",
            "AlgoStyle",
            "TxSpacing",
        ):
            assert rp.get(field).val == 0
        assert rp.Mask.val == 0xFF
        assert rp.FgPen.val == rp.AOlPen.val == -1
        assert rp.DrawMode.val == 1  # NDK JAM2, not COMPLEMENT (2).
        assert rp.LinePtrn.val == 0xFFFF
        assert rp.Font.val == self.font.get_addr()
        assert rp.TxFlags.val == 0x21
        assert rp.TxHeight.val == rp.TxWidth.val == 8
        assert rp.TxBaseline.val == 6
        assert self.mem.r_block(rp.get_addr() + 70, 30) == bytes(30)
        assert self.font.tf_Accessors.val == 7

    def finish(self):
        self.alloc.free_memory(self.block)
        self.font.free()
        assert self.alloc.is_all_free()
        assert not self.alloc.mem_objs
        if self.labels:
            assert not self.labels.get_all_labels()
        if self.machine:
            self.machine.cleanup()


@pytest.fixture(params=[False, True], ids=["unlabelled", "labelled"])
def ctx(request):
    value = Context(request.param)
    yield value
    value.finish()


@pytest.mark.parametrize("previous", [0, 0xA5], ids=["fresh", "reused"])
def graphics_init_rastport_complete_reset_test(ctx, previous):
    ctx.mem.clear_block(ctx.block.addr, ctx.block.size, 0xCC)
    ctx.mem.clear_block(ctx.raster.get_addr(), 100, previous)
    font_before = ctx.mem.r_block(ctx.font.get_addr(), TextFontStruct.get_size())
    ctx.initialize()
    ctx.check_defaults()
    assert ctx.mem.r_block(ctx.block.addr, 4) == b"\xcc" * 4
    assert ctx.mem.r_block(ctx.block.addr + 104, 4) == b"\xcc" * 4
    assert (
        ctx.mem.r_block(ctx.font.get_addr(), TextFontStruct.get_size()) == font_before
    )


@pytest.mark.parametrize("labels", [False, True], ids=["unlabelled", "labelled"])
def graphics_init_rastport_native_entry_test(labels):
    ctx = Context(labels, machine=Machine())
    code = ctx.alloc.alloc_memory(8)
    try:
        ctx.mem.clear_block(ctx.raster.get_addr(), 100, 0xA5)
        calls = []

        def initialize(op, pc):
            calls.append(ctx.cpu.r_reg(REG_A1))
            ctx.graphics.InitRastPort(ctx)

        trap = ctx.machine.setup_quick_trap(initialize)
        # A guest calls the public entry with its RastPort in A1.
        ctx.mem.w16(code.addr, 0x4EB9)
        ctx.mem.w32(code.addr + 2, trap)
        ctx.mem.w16(code.addr + 6, 0x4E75)
        result = Runtime(ctx.machine).start(
            Code(
                code.addr,
                ctx.machine.get_scratch_top(),
                set_regs={REG_A1: ctx.raster.get_addr()},
            )
        )
        assert result.exit
        assert calls == [ctx.raster.get_addr()]
        ctx.check_defaults()
    finally:
        ctx.alloc.free_memory(code)
        ctx.finish()


@pytest.mark.parametrize("depth", [2, 8])
@pytest.mark.parametrize("operation", ["Text", "Draw", "RectFill"])
def graphics_init_rastport_default_pen_rendering_test(
    ctx, monkeypatch, depth, operation
):
    def size(font, text, width, height):
        ctypes.cast(width, ctypes.POINTER(ctypes.c_int))[0] = len(text) * 8
        return 0

    monkeypatch.setitem(
        sys.modules, "sdl2", SimpleNamespace(sdlttf=SimpleNamespace(TTF_SizeUTF8=size))
    )
    ctx.initialize()
    bitmap = BitMapStruct.alloc(ctx.alloc)
    text = ctx.alloc.alloc_cstr("Hi")
    try:
        bitmap.Depth.val = depth
        ctx.raster.BitMap.val = bitmap.get_addr()
        ctx.raster.BgPen.val = -128
        colors = {index: object() for index in range(256)}
        ctx.graphics.palette = colors
        ctx.graphics.font_registry[ctx.font.get_addr()] = object()
        batch = RPBatch()
        ctx.graphics.rp_graphics_map[ctx.raster.get_addr()] = SimpleNamespace(
            batch=batch
        )
        ctx.cpu.w_reg(REG_A1, ctx.raster.get_addr())
        ctx.cpu.w_reg(REG_D0, 0xFF)
        ctx.graphics.SetAPen(ctx)
        ctx.cpu.w_reg(REG_A0, text.addr)
        ctx.cpu.w_reg(REG_D0, 2)
        ctx.cpu.w_reg(REG_D1, 3)
        ctx.cpu.w_reg(REG_D2, 4)
        ctx.cpu.w_reg(REG_D3, 5)
        getattr(ctx.graphics, operation)(ctx)
        expected = colors[(1 << depth) - 1]
        if operation == "Text":
            assert batch.texts[0].fg is expected
            assert batch.texts[0].bg is colors[0x80 & ((1 << depth) - 1)]
            command = batch.texts[0]
        elif operation == "Draw":
            assert batch.draws[0].color is expected
            command = batch.draws[0]
        else:
            assert batch.rectfills[0].color is expected
            command = batch.rectfills[0]
        assert command.draw_mode == 1
    finally:
        ctx.graphics.rp_graphics_map.clear()
        ctx.graphics.font_registry.clear()
        ctx.alloc.free_memory(text)
        bitmap.free()


@pytest.mark.parametrize("pen", [0, 1, 127, 128, 255])
def graphics_set_apen_byte_range_test(ctx, pen):
    ctx.initialize()
    ctx.cpu.w_reg(REG_D0, pen)
    ctx.cpu.w_reg(REG_A1, ctx.raster.get_addr())
    ctx.graphics.SetAPen(ctx)
    assert ctx.mem.r8(ctx.raster.FgPen.get_addr()) == pen
    assert ctx.raster.FgPen.val & 0xFF == pen
