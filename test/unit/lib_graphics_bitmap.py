"""Guest bitmap fonts and templates, including caller-owned font copies."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from amitools.vamos.lib.fonts.convert_topaz import convert
from amitools.vamos.lib.graphics import BitMapStruct, RastPortStruct
from amitools.vamos.lib.graphics_font import load_topaz_font
from amitools.vamos.lib.graphics_surface import RasterSurface
from amitools.vamos.lib.GraphicsLibrary import GraphicsLibrary, RPBatch
from amitools.vamos.lib.intuition import TextFontStruct
from amitools.vamos.machine import (
    REG_A0,
    REG_A1,
    REG_D0,
    REG_D1,
    REG_D2,
    REG_D3,
    REG_D4,
    REG_D5,
)
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.mem import MemoryAlloc


@pytest.fixture
def bitmap():
    ctx = SimpleNamespace(mem=MockMemory(), cpu=MockCPU())
    ctx.alloc = MemoryAlloc(ctx.mem)
    graphics = GraphicsLibrary()
    graphics.alloc = ctx.alloc
    font = load_topaz_font()
    font_addr = graphics._store_font(ctx, font, "topaz.font", 8, 6, 8, font.strike)
    graphics.topaz_font = font_addr
    rp = RastPortStruct.alloc(ctx.alloc)
    bm = BitMapStruct.alloc(ctx.alloc)
    graphics.init_rastport_canonical(ctx, rp.addr)
    assert graphics.init_bitmap_canonical(ctx, bm.addr, 32, 16, 3)
    rp.BitMap.val = bm.addr
    graphics._set_font(ctx, rp.addr, font_addr)
    rp.FgPen.val, rp.BgPen.val = 3, 1
    source = ctx.alloc.alloc_memory(512)
    yield ctx, graphics, rp, bm, source
    graphics.rp_graphics_map.clear()
    graphics._close_font(ctx, font_addr)
    for i in range(bm.Depth.val):
        ctx.alloc.free_mem(bm.Planes[i].val, bm.BytesPerRow.val * bm.Rows.val)
    bm.free()
    rp.free()
    ctx.alloc.free_memory(source)
    assert ctx.alloc.is_all_free()


def pixel(ctx, bm, x, y):
    return sum(
        (
            (
                ctx.mem.r8(bm.Planes[i].val + y * bm.BytesPerRow.val + x // 8)
                >> (7 - (x & 7))
            )
            & 1
        )
        << i
        for i in range(bm.Depth.val)
    )


def graphics_topaz_source_reproduces_asset_test():
    fonts = Path(__file__).parents[2] / "amitools/vamos/lib/fonts"
    info = json.loads((fonts / "TopazDoubleSans-8.json").read_text())
    assert convert(fonts / "TopazDoubleSans-16.hunk") == info
    assert (info["height"], info["width"], info["baseline"]) == (8, 8, 6)
    assert len(info["locations"]) == 225
    assert len(bytes.fromhex(info["data"])) == info["modulo"] * 8


@pytest.mark.parametrize("queued", [False, True])
def graphics_template_snapshot_and_bit_offset_test(bitmap, queued):
    ctx, graphics, rp, bm, source = bitmap
    if queued:
        backing = SimpleNamespace(batch=RPBatch())
        graphics.rp_graphics_map[rp.addr] = backing
    ctx.mem.w_block(source.addr, bytes.fromhex("1c80 0280"))
    for reg, value in [
        (REG_A0, source.addr),
        (REG_A1, rp.addr),
        (REG_D0, 3),
        (REG_D1, 2),
        (REG_D2, 1),
        (REG_D3, 2),
        (REG_D4, 6),
        (REG_D5, 2),
    ]:
        ctx.cpu.w_reg(reg, value)
    graphics.BltTemplate(ctx)
    ctx.mem.clear_block(source.addr, 4, 0)
    if queued:
        command = backing.batch.commands[0]
        surface = RasterSurface(32, 16)
        surface.load(command.state)
        surface.template(
            command.state, command.x, command.y, command.w, command.h, command.pixels
        )
        backing.batch.clear()
    assert [pixel(ctx, bm, x, 2) for x in range(1, 7)] == [3, 3, 3, 1, 1, 3]
    assert [pixel(ctx, bm, x, 3) for x in range(1, 7)] == [1, 1, 1, 3, 1, 3]
    assert pixel(ctx, bm, 0, 2) == pixel(ctx, bm, 7, 2) == 0


def graphics_copied_font_custom_spacing_test(bitmap):
    ctx, graphics, rp, bm, source = bitmap
    copy = TextFontStruct.alloc(ctx.alloc)
    spacing = ctx.alloc.alloc_memory(225 * 2)
    try:
        ctx.mem.w_block(copy.addr, ctx.mem.r_block(rp.Font.val, copy.get_size()))
        for i in range(225):
            ctx.mem.w16(spacing.addr + 2 * i, 6)
        copy.tf_Flags.val |= 0x20
        copy.tf_CharSpace.val = spacing.addr
        graphics._set_font(ctx, rp.addr, copy.addr)
        ctx.mem.w_block(source.addr, b"ABignored")
        ctx.cpu.w_reg(REG_A0, source.addr)
        ctx.cpu.w_reg(REG_A1, rp.addr)
        ctx.cpu.w_reg(REG_D0, 2)
        graphics.TextLength(ctx)
        assert ctx.cpu.r_reg(REG_D0) == 12
        rp.cp_x.val, rp.cp_y.val = 1, 6
        ctx.cpu.w_reg(REG_D0, 2)
        graphics.Text(ctx)
        assert rp.cp_x.val == 13 and rp.cp_y.val == 6
        # A and B both produce ink although this TextFont was never opened
        # by the host, and the second origin uses the caller's six-pixel advance.
        assert any(pixel(ctx, bm, x, y) == 3 for y in range(8) for x in range(1, 7))
        assert any(pixel(ctx, bm, x, y) == 3 for y in range(8) for x in range(7, 13))
        assert all(pixel(ctx, bm, x, y) == 0 for y in range(8) for x in range(15, 32))
    finally:
        ctx.alloc.free_memory(spacing)
        copy.free()
