import ctypes
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.label import LabelManager
from amitools.vamos.lib.GraphicsLibrary import GraphicsLibrary
from amitools.vamos.lib.IntuitionLibrary import IntuitionLibrary
from amitools.vamos.lib.graphics import RastPortStruct, TextAttrStruct
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
    def __init__(self, monkeypatch, labels, machine=None):
        self.machine = machine
        self.mem = machine.get_mem() if machine else MockMemory(size_kib=256)
        self.cpu = machine.get_cpu() if machine else MockCPU()
        self.labels = LabelManager() if labels else None
        self.alloc = MemoryAlloc(
            self.mem,
            addr=machine.get_ram_begin() if machine else 0,
            label_mgr=self.labels,
        )
        self.handles = {}
        self.closed = []
        self.next_handle = 1
        self.attributes = {}
        self.screens = {}
        self.ttf = SimpleNamespace(
            TTF_STYLE_UNDERLINE=4,
            TTF_STYLE_BOLD=1,
            TTF_STYLE_ITALIC=2,
            TTF_OpenFont=self.host_open,
            TTF_CloseFont=self.host_close,
            TTF_FontHeight=lambda font: self.handles[font][1],
            TTF_FontAscent=lambda font: self.handles[font][1] - 2,
            TTF_SizeUTF8=self.host_size,
            TTF_SetFontStyle=Mock(),
            TTF_GetError=lambda: b"missing font",
        )
        monkeypatch.setitem(sys.modules, "sdl2", SimpleNamespace(sdlttf=self.ttf))
        self.graphics = GraphicsLibrary()
        self.graphics.alloc = self.alloc
        self.graphics.fontsPath = "/fonts"
        self.default_attr = self.attribute("topaz.font", 8)
        self.graphics.text_attr = self.default_attr
        self.base_font = self.open_font(self.default_attr)
        assert self.base_font
        self.graphics.topaz_font = self.base_font
        self.intuition = IntuitionLibrary()
        self.intuition.alloc = self.alloc
        self.intuition.graphics_lib = self.graphics

    def host_open(self, path, size):
        if path.endswith(b"missing.ttf"):
            return 0
        handle = self.next_handle
        self.next_handle += 1
        self.handles[handle] = (path, size)
        return handle

    def host_close(self, handle):
        self.closed.append(handle)
        del self.handles[handle]

    def host_size(self, handle, text, width, height):
        size = self.handles[handle][1]
        ctypes.cast(width, ctypes.POINTER(ctypes.c_int))[0] = len(text) * (size // 2)
        ctypes.cast(height, ctypes.POINTER(ctypes.c_int))[0] = size
        return 0

    def attribute(self, name, size):
        attr = TextAttrStruct.alloc(self.alloc)
        text = self.alloc.alloc_cstr(name)
        attr.ta_Name.val = text.addr
        attr.ta_YSize.val = size
        self.attributes[attr.get_addr()] = (attr, text)
        return attr

    def free_attribute(self, attr):
        value, text = self.attributes.pop(attr.get_addr())
        self.alloc.free_memory(text)
        value.free()

    def open_font(self, attr):
        self.cpu.w_reg(REG_A0, attr.get_addr())
        self.graphics.OpenFont(self)
        return self.cpu.r_reg(REG_D0)

    def close_font(self, addr):
        self.cpu.w_reg(REG_A1, addr)
        self.graphics.CloseFont(self)

    def screen(self, attr=None, width=64, height=32):
        screen = self.intuition.create_screen(
            self, width, height, 2, attr.get_addr() if attr else 0, 0, 1, 0
        )
        if screen is not None:
            self.screens[screen.get_addr()] = screen
        return screen

    def close_screen(self, screen):
        self.screens.pop(screen.get_addr())
        self.intuition._free_screen(self, screen)

    def snapshot(self):
        return self.alloc.get_free_bytes(), set(self.alloc.mem_objs), set(self.handles)

    def finish(self):
        for screen in tuple(self.screens.values()):
            self.close_screen(screen)
        self.close_font(self.base_font)
        for attr, _ in tuple(self.attributes.values()):
            self.free_attribute(attr)
        assert not self.handles
        assert not self.graphics.font_registry
        assert not self.intuition._screen_fonts
        assert not self.alloc.mem_objs
        assert self.alloc.is_all_free()
        if self.labels:
            assert not self.labels.get_all_labels()
        if self.machine:
            self.machine.cleanup()


@pytest.fixture(params=[False, True], ids=["unlabelled", "labelled"])
def ctx(monkeypatch, request):
    value = Context(monkeypatch, request.param)
    yield value
    value.finish()


@pytest.fixture(params=[False, True], ids=["unlabelled", "labelled"])
def native_ctx(monkeypatch, request):
    value = Context(monkeypatch, request.param, machine=Machine())
    yield value
    value.finish()


@pytest.mark.parametrize("custom", [False, True])
def intuition_screen_font_metrics_test(ctx, custom):
    attr = ctx.attribute("custom.ttf", 14) if custom else None
    size = 14 if custom else 8
    screen = ctx.screen(attr)
    assert screen is not None
    descriptor = TextAttrStruct(ctx.mem, screen.Font.val)
    assert descriptor.ta_YSize.val == size
    assert ctx.mem.r_cstr(descriptor.ta_Name.val) == (
        "custom.ttf" if custom else "topaz.font"
    )
    raster = screen.RastPort
    assert raster.Font.val != screen.Font.val
    assert raster.Font.val in ctx.graphics.font_registry
    font = TextFontStruct(ctx.mem, raster.Font.val)
    assert font.tf_YSize.val == raster.TxHeight.val == size
    assert font.tf_XSize.val == raster.TxWidth.val == size // 2
    assert font.tf_Baseline.val == raster.TxBaseline.val == size - 2
    assert raster.TxSpacing.val == 0
    assert raster.DrawMode.val == 1
    ctx.close_screen(screen)


def intuition_screen_font_descriptor_lifetime_test(ctx):
    attr = ctx.attribute("custom.ttf", 14)
    name_addr = attr.ta_Name.val
    attr_addr = attr.get_addr()
    screen = ctx.screen(attr)
    ctx.free_attribute(attr)
    # Caller descriptors may be freed/reused once screen creation returns.
    ctx.mem.clear_block(attr_addr, TextAttrStruct.get_size(), 0xA5)
    ctx.mem.clear_block(name_addr, len("custom.ttf") + 1, 0xA5)
    descriptor = TextAttrStruct(ctx.mem, screen.Font.val)
    assert descriptor.ta_YSize.val == 14
    assert ctx.mem.r_cstr(descriptor.ta_Name.val) == "custom.ttf"
    assert TextFontStruct(ctx.mem, screen.RastPort.Font.val).tf_YSize.val == 14
    ctx.close_screen(screen)


def intuition_screen_font_independent_lifetimes_test(ctx):
    first, second = ctx.screen(), ctx.screen()
    first_font, second_font = first.RastPort.Font.val, second.RastPort.Font.val
    ctx.close_screen(first)
    if first_font != second_font:
        assert first_font not in ctx.graphics.font_registry
    assert second_font in ctx.graphics.font_registry
    assert TextFontStruct(ctx.mem, second_font).tf_YSize.val == 8
    ctx.close_screen(second)
    assert set(ctx.graphics.font_registry) == {ctx.base_font}


def intuition_screen_font_public_pointer_change_test(ctx):
    screen = ctx.screen()
    owned_font = screen.RastPort.Font.val
    borrowed_attr = ctx.attribute("custom.ttf", 14)
    borrowed_font = ctx.open_font(borrowed_attr)
    ctx.cpu.w_reg(REG_A0, borrowed_font)
    ctx.cpu.w_reg(REG_A1, screen.RastPort.get_addr())
    ctx.graphics.SetFont(ctx)
    screen.Font.val = borrowed_attr.get_addr()
    ctx.close_screen(screen)
    assert owned_font not in ctx.graphics.font_registry
    assert borrowed_font in ctx.graphics.font_registry
    assert ctx.alloc.get_memory(borrowed_attr.get_addr()) is not None
    ctx.close_font(borrowed_font)


@pytest.mark.parametrize(
    "failure", ["missing", "metrics", "font-memory", "style", "set-font"]
)
def intuition_screen_font_failure_test(ctx, monkeypatch, failure):
    attr = ctx.attribute("missing.ttf" if failure == "missing" else "custom.ttf", 14)
    before = ctx.snapshot()
    if failure == "metrics":
        ctx.ttf.TTF_SizeUTF8 = Mock(return_value=-1)
    elif failure == "font-memory":
        allocate = ctx.alloc.alloc_memory

        def fail(size, **kwargs):
            if kwargs.get("label") == "Graphics TextFont":
                return None
            return allocate(size, **kwargs)

        monkeypatch.setattr(ctx.alloc, "alloc_memory", fail)
    elif failure == "style":
        ctx.ttf.TTF_SetFontStyle.side_effect = RuntimeError("font style")
    elif failure == "set-font":
        monkeypatch.setattr(
            ctx.graphics, "_set_font", Mock(side_effect=RuntimeError("font metrics"))
        )
    if failure in ("style", "set-font"):
        with pytest.raises(RuntimeError):
            ctx.screen(attr)
    else:
        assert ctx.screen(attr) is None
    assert ctx.snapshot() == before
    assert not ctx.intuition._screen_fonts
    if failure == "style":
        ctx.ttf.TTF_SetFontStyle.side_effect = None


@pytest.mark.parametrize("remaining", [356, 364, 400])
def intuition_screen_font_real_exhaustion_test(ctx, remaining):
    # Exhaust the allocator at the copied attributes, copied name, or
    # final 52-byte TextFont, after the tiny screen and planes fit.
    reserve = ctx.alloc.alloc_memory(ctx.alloc.get_free_bytes() - remaining)
    before = ctx.snapshot()
    handles_issued = ctx.next_handle
    assert ctx.screen(width=1, height=1) is None
    assert ctx.snapshot() == before
    assert not ctx.intuition._screen_fonts
    assert ctx.next_handle == handles_issued + (remaining == 400)
    ctx.alloc.free_memory(reserve)


def intuition_screen_font_close_exception_test(ctx):
    screen = ctx.screen()
    close = ctx.ttf.TTF_CloseFont

    def fail(handle):
        close(handle)
        raise RuntimeError("host close")

    ctx.ttf.TTF_CloseFont = fail
    with pytest.raises(RuntimeError, match="host close"):
        ctx.close_screen(screen)
    ctx.ttf.TTF_CloseFont = close
    assert set(ctx.graphics.font_registry) == {ctx.base_font}
    assert not ctx.intuition._screen_fonts


def graphics_set_font_keeps_character_spacing_test(ctx):
    raster = RastPortStruct.alloc(ctx.alloc)
    font = TextFontStruct(ctx.mem, ctx.base_font)
    font.tf_CharSpace.val = 0x123456
    raster.TxSpacing.val = 3
    raster.AlgoStyle.val = 7
    ctx.cpu.w_reg(REG_A0, ctx.base_font)
    ctx.cpu.w_reg(REG_A1, raster.get_addr())
    ctx.graphics.SetFont(ctx)
    assert raster.TxHeight.val == 8
    assert raster.TxSpacing.val == 3
    assert raster.AlgoStyle.val == 0
    raster.free()


@pytest.mark.parametrize("custom", [False, True])
def intuition_screen_font_native_test(native_ctx, custom):
    ctx = native_ctx
    attr = ctx.attribute("custom.ttf", 14) if custom else None
    size = 14 if custom else 8
    screen = ctx.screen(attr)
    program = bytes.fromhex(
        "2268008870003029001472003228008e7400342800907600362800924e75"
    )
    code = ctx.alloc.alloc_memory(len(program))
    try:
        ctx.mem.w_block(code.addr, program)
        # Read Screen.RastPort.Font at SDK offset 136, then tf_YSize at
        # font+20 and the raster's height/width/baseline at 142/144/146.
        result = Runtime(ctx.machine).start(
            Code(
                code.addr,
                ctx.machine.get_scratch_top(),
                set_regs={REG_A0: screen.get_addr()},
                get_regs=[REG_A1, REG_D0, REG_D1, REG_D2, REG_D3],
            )
        )
        assert result.exit
        assert result.regs[REG_A1] in ctx.graphics.font_registry
        assert result.regs[REG_D0] == result.regs[REG_D1] == size
        assert result.regs[REG_D2] == size // 2
        assert result.regs[REG_D3] == size - 2
    finally:
        ctx.alloc.free_memory(code)
    ctx.close_screen(screen)


def intuition_close_screen_rejects_live_windows_test(ctx):
    from amitools.vamos.lib.intuition import WindowStruct
    default = ctx.screen()
    custom = ctx.screen()
    default.NextScreen.val = custom.addr
    ctx.intuition.default_screen = default
    win = WindowStruct.alloc(ctx.alloc)
    try:
        for addr in (default.addr, custom.addr, 0):
            custom.FirstWindow.val = win.addr
            ctx.cpu.w_reg(REG_A0, addr)
            ctx.intuition.CloseScreen(ctx)
            assert ctx.cpu.r_reg(REG_D0) == 0
            assert default.NextScreen.val == custom.addr
        custom.FirstWindow.val = 0
        ctx.cpu.w_reg(REG_A0, custom.addr)
        ctx.intuition.CloseScreen(ctx)
        assert ctx.cpu.r_reg(REG_D0) == 1
        ctx.screens.pop(custom.addr)
        assert default.NextScreen.val == 0
    finally:
        win.free()


def graphics_queued_text_keeps_closed_host_font_alive_test(ctx):
    from amitools.vamos.lib.GraphicsLibrary import RPBatch
    from amitools.vamos.lib.graphics import RastPortStruct
    attr = ctx.attribute('custom.ttf', 10)
    addr = ctx.open_font(attr)
    old_handle = ctx.graphics.font_registry[addr]
    rp = RastPortStruct.alloc(ctx.alloc)
    text = ctx.alloc.alloc_cstr('Hi')
    batch = RPBatch()
    replacement = 0
    try:
        ctx.graphics.init_rastport_canonical(ctx, rp.addr)
        ctx.graphics._set_font(ctx, rp.addr, addr)
        ctx.graphics.palette = {0: object(), 255: object()}
        ctx.graphics.rp_graphics_map[rp.addr] = SimpleNamespace(batch=batch)
        ctx.cpu.w_reg(REG_A0, text.addr)
        ctx.cpu.w_reg(REG_A1, rp.addr)
        ctx.cpu.w_reg(REG_D0, 2)
        ctx.graphics.Text(ctx)
        assert batch.commands
        ctx.close_font(addr)
        assert ctx.alloc.get_memory(addr) is None
        assert old_handle in ctx.handles
        replacement = ctx.open_font(attr)
        replacement_handle = ctx.graphics.font_registry[replacement]
        batch.clear()
        assert old_handle not in ctx.handles
        assert replacement_handle in ctx.handles
        batch.clear()  # A consumed batch cannot close a handle twice.
    finally:
        batch.clear()
        ctx.graphics.rp_graphics_map.pop(rp.addr, None)
        if replacement:
            ctx.close_font(replacement)
        ctx.alloc.free_memory(text)
        rp.free()
