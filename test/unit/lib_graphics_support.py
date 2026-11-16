from types import SimpleNamespace

import pytest

from amitools.fd import read_lib_fd
from amitools.vamos.lib.graphics import BitMapStruct, LayerStruct, RastPortStruct
from amitools.vamos.lib.GraphicsLibrary import GraphicsLibrary
from amitools.vamos.lib.intuition import TextFontStruct
from amitools.vamos.lib.LayersLibrary import LayersLibrary
from amitools.vamos.libcore.impl import LibImplScanner
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.mem import MemoryAlloc


@pytest.fixture
def ctx():
    mem = MockMemory(size_kib=128)
    value = SimpleNamespace(mem=mem, cpu=MockCPU(), alloc=MemoryAlloc(mem))
    value.graphics = GraphicsLibrary()
    yield value
    assert value.alloc.is_all_free()


@pytest.mark.parametrize(
    "name,cls", [("graphics", GraphicsLibrary), ("layers", LayersLibrary)]
)
def graphics_support_vectors_test(name, cls):
    name += ".library"
    scan = LibImplScanner().scan(name, cls(), read_lib_fd(name))
    assert not scan.error_funcs
    assert not scan.invalid_funcs


def graphics_support_bitmap_test(ctx):
    lib = ctx.graphics
    bitmap = lib.AllocBitMap(ctx, 19, 7, 3, 1, 0)
    assert bitmap
    bm = BitMapStruct(ctx.mem, bitmap)
    assert [lib.GetBitMapAttr(ctx, bitmap, n) for n in (0, 4, 8, 12)] == [7, 3, 32, 1]
    assert len({bm.Planes[i].val for i in range(3)}) == 3
    assert all(
        bytes(ctx.mem.r_block(bm.Planes[i].val, 28)) == bytes(28) for i in range(3)
    )
    lib.FreeBitMap(ctx, bitmap)
    assert lib.GetBitMapAttr(ctx, 0, 4) == 0
    assert lib.AllocBitMap(ctx, 19, 7, 0, 0, 0) == 0


def graphics_support_bitmap_partial_failure_test(ctx, monkeypatch):
    allocate = ctx.alloc.alloc_mem
    count = 0

    def fail_second_plane(size, *args, **kwargs):
        nonlocal count
        count += 1
        # Bitmap descriptor, first plane, then failed second plane.
        return 0 if count == 3 else allocate(size, *args, **kwargs)

    monkeypatch.setattr(ctx.alloc, "alloc_mem", fail_second_plane)
    assert not ctx.graphics.AllocBitMap(ctx, 32, 8, 3, 1, 0)
    assert not ctx.graphics._bitmaps


@pytest.mark.parametrize("minterm,expected", [(0xE0, 0x80), (0x20, 0x40)])
def graphics_support_masked_blit_test(ctx, minterm, expected):
    lib = ctx.graphics
    source = lib.AllocBitMap(ctx, 16, 2, 2, 1, 0)
    dest = lib.AllocBitMap(ctx, 16, 2, 3, 1, 0)
    src, dst = BitMapStruct(ctx.mem, source), BitMapStruct(ctx.mem, dest)
    # Two alternating colors and a mask covering only the first two pixels.
    ctx.mem.w8(src.Planes[0].val, 0xAA)
    ctx.mem.w8(src.Planes[1].val, 0x55)
    ctx.mem.w8(dst.Planes[2].val + 2, 0xFF)
    mask = ctx.alloc.alloc_memory(4)
    ctx.mem.w8(mask.addr, 0xC0)
    port = RastPortStruct.alloc(ctx.alloc)
    port.BitMap.val, port.Mask.val, port.DrawMode.val = dest, 7, 2
    lib.BltMaskBitMapRastPort(
        ctx, source, 0, 0, port.addr, 0, 1, 16, 1, minterm, mask.addr
    )
    assert ctx.mem.r8(dst.Planes[0].val + 2) == expected
    assert ctx.mem.r8(dst.Planes[1].val + 2) == expected ^ 0xC0
    assert ctx.mem.r8(dst.Planes[2].val + 2) == 0xFF
    assert ctx.mem.r16(dst.Planes[0].val) == 0
    port.free()
    ctx.alloc.free_memory(mask)
    lib.FreeBitMap(ctx, source)
    lib.FreeBitMap(ctx, dest)


def graphics_support_masked_blit_snapshot_test(ctx):
    from amitools.vamos.lib.graphics_surface import RasterSurface

    lib = ctx.graphics
    source = lib.AllocBitMap(ctx, 16, 1, 1, 1, 0)
    dest = lib.AllocBitMap(ctx, 16, 1, 1, 1, 0)
    src, dst = BitMapStruct(ctx.mem, source), BitMapStruct(ctx.mem, dest)
    ctx.mem.w8(src.Planes[0].val, 0xFF)
    mask = ctx.alloc.alloc_memory(2)
    ctx.mem.w8(mask.addr, 0xF0)
    port = RastPortStruct.alloc(ctx.alloc)
    port.BitMap.val, port.Mask.val = dest, 1
    commands = []
    lib.rp_graphics_map[port.addr] = SimpleNamespace(
        batch=SimpleNamespace(add=commands.append)
    )
    lib.BltMaskBitMapRastPort(
        ctx, source, 0, 0, port.addr, 0xFFFF, 0, 8, 1, 0xE0, mask.addr
    )
    lib.FreeBitMap(ctx, source)
    ctx.alloc.free_memory(mask)
    command = commands[0]
    surface = RasterSurface(16, 1)
    surface.bitmap_blit(
        command.state,
        command.x,
        command.y,
        command.w,
        command.h,
        command.pixels,
        command.mask,
        SimpleNamespace(x=1, y=0, w=5, h=1),
    )
    assert ctx.mem.r8(dst.Planes[0].val) == 0x60
    del lib.rp_graphics_map[port.addr]
    port.free()
    lib.FreeBitMap(ctx, dest)


def graphics_support_palette_test(ctx):
    lib = ctx.graphics
    cm = lib.GetColorMap(ctx, 4)
    assert ctx.mem.r16(cm + 2) == 4
    lib.SetRGB32CM(ctx, cm, 1, 0x12121212, 0xABABABAB, 0xFFFFFFFF)
    assert lib.GetRGB4(ctx, cm, 1) == 0x1AF
    result = ctx.alloc.alloc_memory(24)
    lib.GetRGB32(ctx, cm, 0, 2, result.addr)
    assert [ctx.mem.r32(result.addr + i * 4) for i in range(6)] == [
        0,
        0,
        0,
        0x12121212,
        0xABABABAB,
        0xFFFFFFFF,
    ]
    assert lib.ObtainBestPenA(ctx, cm, 0x11111111, 0xAAAAAAAA, 0xFFFFFFFF, 0) == 1
    assert lib._pen_refs[cm][1] == 1
    lib.ReleasePen(ctx, cm, 1)
    assert lib._pen_refs[cm][1] == 0
    # A strict request cannot silently return an unsuitable pen.
    ctx.mem.w32(result.addr, 0x84000001)
    ctx.mem.w32(result.addr + 4, 1)
    ctx.mem.w32(result.addr + 8, 0)
    assert lib.ObtainBestPenA(ctx, cm, 0xFFFFFFFF, 0, 0, result.addr) == 0xFFFFFFFF
    # Guest palette table writes remain visible through the query API.
    ctx.mem.w16(ctx.mem.r32(cm + 4) + 2, 0xF00)
    assert lib.GetRGB4(ctx, cm, 1) == 0xF00
    lib.FreeColorMap(ctx, cm)
    ctx.alloc.free_memory(result)
    assert not lib._color_maps and not lib._pen_refs


def graphics_support_text_fit_test(ctx):
    lib = ctx.graphics
    font = TextFontStruct.alloc(ctx.alloc)
    font.tf_LoChar.val, font.tf_HiChar.val = 32, 126
    font.tf_YSize.val, font.tf_XSize.val, font.tf_Baseline.val = 8, 8, 6
    port = RastPortStruct.alloc(ctx.alloc)
    port.Font.val = font.addr
    text = ctx.alloc.alloc_cstr("ABCDE")
    extent = ctx.alloc.alloc_memory(12)
    constraint = ctx.alloc.alloc_memory(12)
    lib.TextExtent(ctx, port.addr, text.addr, 5, extent.addr)
    assert [ctx.mem.r16(extent.addr + i * 2) for i in range(6)] == [
        40,
        8,
        0,
        65530,
        39,
        1,
    ]
    assert lib.TextFit(ctx, port.addr, text.addr, 5, extent.addr, 0, 1, 24, 8) == 3
    assert ctx.mem.r16(extent.addr) == 24
    assert (
        lib.TextFit(ctx, port.addr, text.addr + 4, 5, extent.addr, 0, 0xFFFF, 16, 8)
        == 2
    )
    assert lib.TextFit(ctx, port.addr, text.addr, 5, extent.addr, 0, 1, 40, 7) == 0
    lib._write_extent(ctx, constraint.addr, (16, 8, 0, -6, 39, 1))
    assert (
        lib.TextFit(
            ctx, port.addr, text.addr, 5, extent.addr, constraint.addr, 1, 40, 8
        )
        == 2
    )
    # These calls must not move the drawing position or alter the pens.
    lib.SetABPenDrMd(ctx, port.addr, 255, 128, 2)
    assert (
        lib.GetAPen(ctx, port.addr),
        lib.GetBPen(ctx, port.addr),
        lib.GetDrMd(ctx, port.addr),
    ) == (255, 128, 2)
    assert (port.cp_x.val, port.cp_y.val) == (0, 0)
    for memory in (font, port):
        memory.free()
    for memory in (text, extent, constraint):
        ctx.alloc.free_memory(memory)


def graphics_support_pixel_test(ctx):
    lib = ctx.graphics
    bm = lib.AllocBitMap(ctx, 16, 2, 2, 1, 0)
    port = RastPortStruct.alloc(ctx.alloc)
    port.BitMap.val, port.Mask.val = bm, 3
    lib.SetABPenDrMd(ctx, port.addr, 3, 0, 0)
    assert lib.WritePixel(ctx, port.addr, 5, 1) == 0
    bitmap = BitMapStruct(ctx.mem, bm)
    for i in range(2):
        assert ctx.mem.r8(bitmap.Planes[i].val + 2) == 4
    lib.SetABPenDrMd(ctx, port.addr, 1, 0, 2)
    lib.WritePixel(ctx, port.addr, 5, 1)
    for i in range(2):
        assert ctx.mem.r8(bitmap.Planes[i].val + 2) == 0
    assert lib.WritePixel(ctx, port.addr, 0xFFFF, 0) == 0xFFFFFFFF
    lib.FreeBitMap(ctx, bm)
    port.free()


def graphics_support_install_clip_test(ctx, monkeypatch):
    import sys

    monkeypatch.setitem(
        sys.modules, "sdl2", SimpleNamespace(SDL_Rect=lambda x, y, w, h: (x, y, w, h))
    )
    lib = ctx.graphics
    layer = LayerStruct.alloc(ctx.alloc)
    layer.rp.val = 123
    backing = SimpleNamespace(user_clip_rects=None)
    lib.rp_graphics_map[123] = backing
    flushed = []
    ctx.exec_lib = SimpleNamespace(
        graphics_lib=lib,
        intuition_lib=SimpleNamespace(
            _flush_batch=lambda backing: flushed.append(backing.user_clip_rects)
        ),
    )
    region = lib._new_region(ctx)
    lib._replace_region(ctx, region, [(2, 3, 9, 7)])
    layers = LayersLibrary()
    assert layers.InstallClipRegion(ctx, layer.addr, region) == 0
    assert layer.ClipRegion.val == region
    assert backing.user_clip_rects == [(2, 3, 8, 5)]
    assert layers.InstallClipRegion(ctx, layer.addr, 0) == region
    assert flushed == [None, [(2, 3, 8, 5)]]
    assert backing.user_clip_rects is None
    lib._dispose_region(ctx, region)
    layer.free()
