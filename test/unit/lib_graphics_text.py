import ctypes
import sys
from types import SimpleNamespace

import pytest

from amitools.vamos.lib.GraphicsLibrary import GraphicsLibrary, RPBatch
from amitools.vamos.lib.graphics import RastPortStruct
from amitools.vamos.lib.intuition import TextFontStruct
from amitools.vamos.machine import REG_A0, REG_A1, REG_D0
from amitools.vamos.machine.mock import MockMemory, MockCPU
from amitools.vamos.mem import MemoryAlloc


@pytest.fixture
def ctx(monkeypatch):
    ctx = SimpleNamespace(mem=MockMemory(), cpu=MockCPU(), measured=[], fail=False)
    ctx.alloc = MemoryAlloc(ctx.mem)
    ctx.font = TextFontStruct.alloc(ctx.alloc)
    ctx.rp = RastPortStruct.alloc(ctx.alloc)
    ctx.text = ctx.alloc.alloc_memory(32)
    ctx.graphics = GraphicsLibrary()
    ctx.graphics.alloc = ctx.alloc
    ctx.graphics.topaz_font = ctx.font.get_addr()
    ctx.graphics.font_registry[ctx.font.get_addr()] = object()
    ctx.graphics.palette = {255: object(), 0: object()}
    ctx.font.tf_Baseline.val = 6
    ctx.graphics.init_rastport_canonical(ctx, ctx.rp.get_addr())
    ctx.rp.cp_x.val, ctx.rp.cp_y.val = 4, 12
    ctx.batch = RPBatch()
    ctx.graphics.rp_graphics_map[ctx.rp.get_addr()] = SimpleNamespace(batch=ctx.batch)
    ctx.cpu.w_reg(REG_A0, ctx.text.addr)
    ctx.cpu.w_reg(REG_A1, ctx.rp.get_addr())

    def size(font, text, width, height):
        text = text.decode("utf-8")
        ctx.measured.append(text)
        # Exercise proportional metrics, not count * nominal font width.
        ctypes.cast(width, ctypes.POINTER(ctypes.c_int))[0] = sum(
            {"i": 3, "W": 11}.get(char, 8) for char in text
        )
        return -1 if ctx.fail else 0

    monkeypatch.setitem(
        sys.modules, "sdl2", SimpleNamespace(sdlttf=SimpleNamespace(TTF_SizeUTF8=size))
    )
    yield ctx
    ctx.alloc.free_memory(ctx.text)
    ctx.rp.free()
    ctx.font.free()
    assert ctx.alloc.is_all_free()


@pytest.mark.parametrize("operation", ["Text", "TextLength"])
@pytest.mark.parametrize(
    "data,count,expected,width",
    [
        (b"HiEXTRA", 2, "Hi", 11),
        (b"Wi", 2, "Wi", 14),
        (b"A\xe9Z", 2, "A\xe9", 16),
        (b"A\0B", 3, "A\ufffdB", 24),
    ],
)
def graphics_text_counted_bytes_test(
    ctx, monkeypatch, operation, data, count, expected, width
):
    ctx.mem.w_block(ctx.text.addr, data)
    original = ctx.mem.r_block

    def bounded(addr, size):
        assert (addr, size) == (ctx.text.addr, count)
        return original(addr, size)

    monkeypatch.setattr(ctx.mem, "r_block", bounded)
    monkeypatch.setattr(ctx.mem, "r_cstr", lambda addr: pytest.fail("unbounded read"))
    ctx.cpu.w_reg(REG_D0, count)
    getattr(ctx.graphics, operation)(ctx)
    assert ctx.measured == [expected]
    if operation == "Text":
        assert ctx.batch.texts[0].string == expected
        assert (ctx.batch.texts[0].x, ctx.batch.texts[0].y) == (4, 6)
        assert (ctx.rp.cp_x.val, ctx.rp.cp_y.val) == (4 + width, 12)
    else:
        assert ctx.cpu.r_reg(REG_D0) == width
        assert (ctx.rp.cp_x.val, ctx.rp.cp_y.val) == (4, 12)
        assert not ctx.batch.texts


@pytest.mark.parametrize("operation", ["Text", "TextLength"])
def graphics_text_zero_count_test(ctx, monkeypatch, operation):
    ctx.cpu.w_reg(REG_D0, 0)
    ctx.cpu.w_reg(REG_A0, 0xDEADBEEF)
    ctx.cpu.w_reg(REG_A1, 0xDEADBEEF)
    monkeypatch.delitem(sys.modules, "sdl2")
    monkeypatch.setattr(ctx.mem, "r_block", lambda *args: pytest.fail("zero read"))
    getattr(ctx.graphics, operation)(ctx)
    assert not ctx.measured
    assert not ctx.batch.texts


@pytest.mark.parametrize("spacing", [-2, 0, 3])
def graphics_text_spacing_and_width_agree_test(ctx, spacing):
    ctx.mem.w_block(ctx.text.addr, b"Wi")
    ctx.rp.TxSpacing.val = spacing
    ctx.cpu.w_reg(REG_D0, 2)
    ctx.graphics.TextLength(ctx)
    assert ctx.cpu.r_reg(REG_D0) == 14 + 2 * spacing
    ctx.cpu.w_reg(REG_D0, 2)
    ctx.graphics.Text(ctx)
    assert ctx.rp.cp_x.val == 18 + 2 * spacing
    if spacing:
        assert [t.x for t in ctx.batch.texts] == [4, 15 + spacing]
        assert [t.string for t in ctx.batch.texts] == ["W", "i"]


@pytest.mark.parametrize("operation", ["Text", "TextLength"])
@pytest.mark.parametrize("failure", ["font", "metrics"])
def graphics_text_failure_is_atomic_test(ctx, operation, failure):
    ctx.mem.w_block(ctx.text.addr, b"Hi")
    ctx.cpu.w_reg(REG_D0, 2)
    if failure == "font":
        ctx.graphics.font_registry.clear()
    else:
        ctx.fail = True
    getattr(ctx.graphics, operation)(ctx)
    assert (ctx.rp.cp_x.val, ctx.rp.cp_y.val) == (4, 12)
    assert not ctx.batch.texts
    if operation == "TextLength":
        assert ctx.cpu.r_reg(REG_D0) == 0


def graphics_text_word_position_wrap_test(ctx):
    ctx.mem.w_block(ctx.text.addr, b"Wi")
    ctx.rp.cp_x.val = 32760
    ctx.cpu.w_reg(REG_D0, 2)
    ctx.graphics.Text(ctx)
    assert ctx.rp.cp_x.val == -32762
    assert ctx.rp.cp_y.val == 12


def intuition_print_itext_count_and_state_test(ctx):
    from amitools.vamos.lib.IntuitionLibrary import IntuitionLibrary
    from amitools.vamos.lib.intuition import IntuiTextStruct
    from amitools.vamos.machine import REG_D1

    lib = IntuitionLibrary()
    lib.graphics_lib = ctx.graphics
    items = [IntuiTextStruct.alloc(ctx.alloc) for _ in range(2)]
    try:
        ctx.mem.w_cstr(ctx.text.addr, "Wi")
        for index, item in enumerate(items):
            item.LeftEdge.val = -2
            item.TopEdge.val = 3 + index * 9
            item.IText.set(ctx.text.addr)
            item.FrontPen.val = 255
            item.BackPen.val = 0
            item.DrawMode.val = 1
        items[0].NextText.val = items[1].addr
        before = ctx.mem.r_block(ctx.rp.addr, ctx.rp.get_size())
        ctx.cpu.w_reg(REG_A0, ctx.rp.addr)
        ctx.cpu.w_reg(REG_A1, items[0].addr)
        ctx.cpu.w_reg(REG_D0, 0xFFFF)
        ctx.cpu.w_reg(REG_D1, 5)
        lib.PrintIText(ctx)
        assert [t.string for t in ctx.batch.texts] == ["Wi", "Wi"]
        assert [(t.x, t.y) for t in ctx.batch.texts] == [(-3, 8), (-3, 17)]
        assert ctx.mem.r_block(ctx.rp.addr, ctx.rp.get_size()) == before
    finally:
        for item in items:
            item.free()
