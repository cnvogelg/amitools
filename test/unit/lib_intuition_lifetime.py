import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.label import LabelManager
from amitools.vamos.lib.IntuitionLibrary import IntuitionLibrary
from amitools.vamos.lib.GraphicsLibrary import GraphicsLibrary
from amitools.vamos.lib.graphics import TextAttrStruct
from amitools.vamos.lib.intuition import NewScreenStruct, TextFontStruct
from amitools.vamos.machine import REG_A0, REG_D0
from amitools.vamos.machine.mock import MockMemory, MockCPU
from amitools.vamos.mem import MemoryAlloc


class Context:
    def __init__(self, monkeypatch, labels, size_kib=512):
        self.mem = MockMemory(size_kib=size_kib)
        self.cpu = MockCPU()
        self.labels = LabelManager() if labels else None
        self.alloc = MemoryAlloc(self.mem, label_mgr=self.labels)
        self.graphics = None
        self.references = 0
        self.font_refs = 0
        self.available = True
        self.events = []
        self.exec_lib = SimpleNamespace(graphics_lib=None)
        self.lib_mgr = SimpleNamespace(
            open_lib=self.open_graphics, close_lib=self.close_graphics
        )
        self.sdl = SimpleNamespace(
            SDL_INIT_VIDEO=2,
            SDL_INIT_TIMER=1,
            SDL_Init=Mock(return_value=0),
            SDL_QuitSubSystem=Mock(
                side_effect=lambda flags: self.events.append("quit")
            ),
        )
        monkeypatch.setitem(sys.modules, "sdl2", self.sdl)
        self.lib = IntuitionLibrary()
        self.lib.setup_lib(self, 0)

    def open_graphics(self, name):
        assert name == "graphics.library"
        self.events.append("open")
        if not self.available:
            return 0
        self.references += 1
        attr = TextAttrStruct.alloc(self.alloc)
        font = TextFontStruct.alloc(self.alloc)
        attr.ta_YSize.val = font.tf_YSize.val = 8
        self.graphics = SimpleNamespace(
            text_attr=attr,
            font=font,
            topaz_font=font.get_addr(),
            _open_font=self.acquire_font,
            _close_font=self.release_font,
            _set_font=lambda ctx, rp, font: GraphicsLibrary._set_font(
                self.graphics, ctx, rp, font
            ),
        )
        self.font_refs = 1
        self.exec_lib.graphics_lib = self.graphics
        return 0x1234

    def close_graphics(self, addr):
        assert addr == 0x1234
        self.events.append("close")
        self.references -= 1
        assert self.font_refs == 1
        self.font_refs = 0
        self.graphics.font.free()
        self.graphics.text_attr.free()

    def acquire_font(self, ctx, attr_addr):
        self.font_refs += 1
        return self.graphics.topaz_font

    def release_font(self, ctx, font_addr):
        assert font_addr == self.graphics.topaz_font
        self.font_refs -= 1

    def all_free(self):
        assert self.references == 0
        assert self.font_refs == 0
        assert self.alloc.is_all_free()
        assert not self.alloc.mem_objs
        if self.labels:
            assert not self.labels.get_all_labels()
        assert not self.lib._lib_opened
        assert self.lib.default_screen is None
        assert self.lib.graphics_lib is None
        assert self.lib.graphics_lib_addr is None
        assert not self.lib._screen_fonts


@pytest.fixture(params=[False, True], ids=["unlabelled", "labelled"])
def ctx(monkeypatch, request):
    return Context(monkeypatch, request.param)


def intuition_lifetime_reopen_test(ctx):
    old_memory = None
    for _ in range(2):
        ctx.lib.open_lib(ctx, 1)
        assert ctx.lib._lib_opened
        assert ctx.references == 1
        memory = ctx.alloc.get_memory(ctx.lib.default_screen.get_addr())
        assert memory is not old_memory
        old_memory = memory
        ctx.lib.close_lib(ctx, 0)
        ctx.all_free()
    assert ctx.events == ["open", "close", "quit", "open", "close", "quit"]
    assert ctx.sdl.SDL_Init.call_count == ctx.sdl.SDL_QuitSubSystem.call_count == 2


def intuition_lifetime_remaining_reference_test(ctx):
    ctx.lib.open_lib(ctx, 1)
    screen = ctx.lib.default_screen
    ctx.lib.open_lib(ctx, 2)
    ctx.lib.close_lib(ctx, 1)
    assert ctx.lib.default_screen is screen
    assert ctx.lib._lib_opened
    assert ctx.references == 1
    assert ctx.sdl.SDL_Init.call_count == 1
    ctx.sdl.SDL_QuitSubSystem.assert_not_called()
    ctx.lib.close_lib(ctx, 0)
    ctx.all_free()


@pytest.mark.parametrize(
    "failure", ["no-binding", "video", "graphics", "title", "screen"]
)
def intuition_lifetime_headless_failure_test(ctx, monkeypatch, failure):
    if failure == "no-binding":
        monkeypatch.setitem(sys.modules, "sdl2", None)
    elif failure == "video":
        ctx.sdl.SDL_Init.return_value = -1
    elif failure == "graphics":
        ctx.available = False
    else:
        allocate = ctx.alloc.alloc_memory
        failed_label = (
            "Intuition default title" if failure == "title" else "Intuition screen"
        )

        def fail(size, **kwargs):
            if kwargs.get("label") == failed_label:
                return None
            return allocate(size, **kwargs)

        monkeypatch.setattr(ctx.alloc, "alloc_memory", fail)
    ctx.lib.open_lib(ctx, 1)
    assert ctx.lib.default_screen is None
    assert not ctx.lib._lib_opened
    ctx.lib.close_lib(ctx, 0)
    ctx.all_free()
    assert ctx.sdl.SDL_QuitSubSystem.call_count == (
        0 if failure in ("no-binding", "video") else 1
    )


def intuition_lifetime_partial_bitmap_failure_test(ctx, monkeypatch):
    # A default plane needs 60,000 bytes. One fits; the second does not.
    small = Context(monkeypatch, ctx.labels is not None, size_kib=70)
    allocate = small.alloc.alloc_mem
    planes = []

    def record(size, *args, **kwargs):
        addr = allocate(size, *args, **kwargs)
        if size == 60000 and addr:
            planes.append(addr)
        return addr

    monkeypatch.setattr(small.alloc, "alloc_mem", record)
    small.lib.open_lib(small, 1)
    assert len(planes) == 1
    small.all_free()
    # A later attempt may succeed once a smaller display is requested.
    create = small.lib.create_screen

    def smaller(ctx_arg, width, height, depth, *args, **kwargs):
        return create(ctx_arg, 64, 32, 2, *args, **kwargs)

    monkeypatch.setattr(small.lib, "create_screen", smaller)
    small.lib.open_lib(small, 1)
    assert small.lib._lib_opened
    small.lib.close_lib(small, 0)
    small.all_free()


def intuition_lifetime_setup_exception_test(ctx, monkeypatch):
    monkeypatch.setattr(
        ctx.alloc, "alloc_memory", Mock(side_effect=RuntimeError("allocate"))
    )
    with pytest.raises(RuntimeError, match="allocate"):
        ctx.lib.open_lib(ctx, 1)
    ctx.all_free()
    assert ctx.events == ["open", "close", "quit"]


def intuition_lifetime_close_exception_test(ctx):
    ctx.lib.open_lib(ctx, 1)

    def close(addr):
        ctx.close_graphics(addr)
        raise RuntimeError("close graphics")

    ctx.lib_mgr.close_lib = close
    with pytest.raises(RuntimeError, match="close graphics"):
        ctx.lib.close_lib(ctx, 0)
    ctx.all_free()
    assert ctx.events == ["open", "close", "quit"]
    ctx.lib.close_lib(ctx, 0)
    ctx.all_free()


def intuition_lifetime_borrowed_title_test(ctx):
    ctx.lib.open_lib(ctx, 1)
    borrowed = ctx.alloc.alloc_cstr("caller title")
    ctx.lib.default_screen.DefaultTitle.val = borrowed.addr
    ctx.lib.close_lib(ctx, 0)
    assert ctx.alloc.get_memory(borrowed.addr) is borrowed
    assert ctx.mem.r_cstr(borrowed.addr) == "caller title"
    ctx.alloc.free_memory(borrowed)
    ctx.all_free()


@pytest.mark.parametrize("method", ["OpenWindow", "OpenWindowTagList", "OpenScreen"])
def intuition_lifetime_headless_window_test(ctx, monkeypatch, method):
    monkeypatch.setitem(sys.modules, "sdl2", None)
    ctx.lib.open_lib(ctx, 1)
    getattr(ctx.lib, method)(ctx)
    assert ctx.cpu.r_reg(REG_D0) == 0
    ctx.lib.close_lib(ctx, 0)
    ctx.all_free()


@pytest.mark.parametrize("exhausted", [False, True])
def intuition_lifetime_custom_screen_test(ctx, exhausted):
    ctx.lib.open_lib(ctx, 1)
    new_screen = NewScreenStruct.alloc(ctx.alloc)
    title = ctx.alloc.alloc_cstr("custom title")
    new_screen.Width.val = 4096 if exhausted else 64
    new_screen.Height.val = 4096 if exhausted else 32
    new_screen.Depth.val = 2
    new_screen.Font.val = ctx.graphics.text_attr.get_addr()
    new_screen.DefaultTitle.val = title.addr
    ctx.cpu.w_reg(REG_A0, new_screen.get_addr())
    ctx.lib.OpenScreen(ctx)
    assert bool(ctx.cpu.r_reg(REG_D0)) == (not exhausted)
    # Closing the library releases its default and any remaining custom
    # screens, while the input structure and caller's title stay borrowed.
    ctx.lib.close_lib(ctx, 0)
    assert set(ctx.alloc.mem_objs) == {new_screen.get_addr(), title.addr}
    assert ctx.mem.r_cstr(title.addr) == "custom title"
    new_screen.free()
    ctx.alloc.free_memory(title)
    ctx.all_free()
