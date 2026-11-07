import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.label import LabelManager
from amitools.vamos.lib.GraphicsLibrary import GraphicsLibrary
from amitools.vamos.lib.IntuitionLibrary import IntuitionLibrary
from amitools.vamos.lib.graphics import RastPortStruct, LayerStruct, RectangleStruct
from amitools.vamos.lib.intuition import (
    IDCMP_NEWSIZE,
    IDCMP_CLOSEWINDOW,
    ScreenStruct,
    TextFontStruct,
    WindowStruct,
)
from amitools.vamos.lib.lexec.msgfunc import MessageFunc
from amitools.vamos.lib.lexec.PortManager import PortManager
from amitools.vamos.machine import REG_A0
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.mem import MemoryAlloc


class WindowContext:
    def __init__(self, monkeypatch, labels):
        self.mem = MockMemory(size_kib=256)
        self.cpu = MockCPU()
        self.labels = LabelManager() if labels else None
        self.alloc = MemoryAlloc(self.mem, label_mgr=self.labels)
        self.task = None
        self.font = TextFontStruct.alloc(self.alloc)
        self.font.tf_YSize.val = 8
        self.font.tf_XSize.val = 8
        self.font.tf_Baseline.val = 6
        self.screen = ScreenStruct.alloc(self.alloc)
        self.screen.Width.val = 64
        self.screen.Height.val = 32
        self.base_free = self.alloc.get_free_bytes()
        self.base_objects = set(self.alloc.mem_objs)
        self.base_labels = self.labels.get_all_labels() if labels else []
        self.events = []
        self.windows = set()
        self.timers = set()
        self.renderers = set()
        self.textures = set()
        self.next_window_id = 7
        self.next_timer_id = 1000
        self.next_texture = 2000
        self.sdl = SimpleNamespace(
            SDL_WINDOWPOS_CENTERED=0,
            SDL_RENDERER_ACCELERATED=1,
            SDL_RENDERER_PRESENTVSYNC=2,
            SDL_PIXELFORMAT_RGBA8888=0,
            SDL_TEXTUREACCESS_TARGET=1,
            SDL_MOUSEMOTION=1,
            SDL_MOUSEBUTTONDOWN=2,
            SDL_MOUSEBUTTONUP=3,
            SDL_KEYDOWN=4,
            SDL_QUIT=5,
            SDL_WINDOWEVENT=6,
            SDL_WINDOWEVENT_RESIZED=10,
            SDL_WINDOWEVENT_EXPOSED=11,
            SDL_WINDOWEVENT_CLOSE=12,
            SDL_CreateWindow=self.create_host_window,
            SDL_GetWindowID=lambda window: window,
            SDL_DestroyWindow=self.destroy_host_window,
            SDL_AddTimer=self.add_timer,
            SDL_RemoveTimer=self.remove_timer,
            SDL_CreateRenderer=self.create_renderer,
            SDL_CreateTexture=self.create_texture,
            SDL_DestroyRenderer=self.destroy_renderer,
            SDL_DestroyTexture=self.destroy_texture,
            SDL_SetRenderTarget=Mock(),
            SDL_SetRenderDrawColor=Mock(),
            SDL_RenderClear=Mock(),
        )
        monkeypatch.setitem(sys.modules, "sdl2", self.sdl)
        signal = SimpleNamespace(get_my_sched_task=lambda: None, signal=Mock())
        task = SimpleNamespace(find_task=lambda name: None)
        self.messages = MessageFunc(self, None, signal, task, PortManager(self.alloc))
        self.exec_lib = SimpleNamespace(
            CreateMsgPort=lambda ctx: self.messages.create_msg_port(),
            DeleteMsgPort=self.delete_port,
            msg_func=self.messages,
            register_SDL_poll=Mock(),
        )
        self.graphics = GraphicsLibrary()
        self.graphics.alloc = self.alloc
        self.graphics.topaz_font = self.font.get_addr()
        self.intuition = IntuitionLibrary()
        self.intuition.alloc = self.alloc
        self.intuition.graphics_lib = self.graphics
        self.intuition.default_screen = self.screen

    def create_host_window(self, *args):
        window_id = self.next_window_id
        self.next_window_id += 1
        self.windows.add(window_id)
        return window_id

    def destroy_host_window(self, window):
        self.events.append(("window", window))
        self.windows.remove(window)

    def add_timer(self, interval, callback, param):
        timer = self.next_timer_id
        self.next_timer_id += 1
        self.timers.add(timer)
        return timer

    def remove_timer(self, timer):
        self.events.append(("timer", timer))
        self.timers.remove(timer)
        return True

    def create_renderer(self, window, *args):
        self.renderers.add(window)
        return window

    def destroy_renderer(self, renderer):
        self.events.append(("renderer", renderer))
        self.renderers.remove(renderer)

    def create_texture(self, *args):
        texture = self.next_texture
        self.next_texture += 1
        self.textures.add(texture)
        return texture

    def destroy_texture(self, texture):
        self.events.append(("texture", texture))
        self.textures.remove(texture)

    def delete_port(self, ctx, port):
        self.events.append(("port", port.get_addr()))
        self.messages.delete_msg_port(port)

    def open(self):
        return self.intuition.create_window_struct(
            self,
            0,
            0,
            64,
            32,
            IDCMP_NEWSIZE | IDCMP_CLOSEWINDOW,
            "test",
            self.screen.get_addr(),
            0,
        )

    def close(self, addr):
        self.cpu.w_reg(REG_A0, addr)
        self.intuition.CloseWindow(self)

    def resize(self, window_id, width=123, height=45):
        return SimpleNamespace(
            type=self.sdl.SDL_WINDOWEVENT,
            window=SimpleNamespace(
                windowID=window_id,
                event=self.sdl.SDL_WINDOWEVENT_RESIZED,
                data1=width,
                data2=height,
            ),
        )

    def close_all(self):
        for addr in tuple(self.intuition.sdl_window_id_2_window_addr_map.values()):
            self.close(addr)
        assert self.screen.FirstWindow.val == 0
        assert self.alloc.get_free_bytes() == self.base_free
        assert set(self.alloc.mem_objs) == self.base_objects
        if self.labels:
            assert self.labels.get_all_labels() == self.base_labels
        assert not self.windows
        assert not self.timers
        assert not self.renderers
        assert not self.textures
        assert not self.intuition.rp_2_win_addr
        assert not self.intuition.refresh_pending
        assert not self.intuition.sdl_window_id_2_sdl_window
        self.screen.free()
        self.font.free()
        assert self.alloc.is_all_free()
        assert not self.alloc.mem_objs
        if self.labels:
            assert not self.labels.get_all_labels()


@pytest.fixture(params=[False, True], ids=["unlabelled", "labelled"])
def ctx(monkeypatch, request):
    return WindowContext(monkeypatch, request.param)


@pytest.mark.parametrize("index", [0, 1, 2])
def intuition_close_window_resources_test(ctx, index):
    windows = [ctx.open() for _ in range(3)]
    target = windows[index]
    window_id = ctx.intuition.find_sdl_window_by_amiga_addr(target)
    ctx.intuition.refresh_pending.update(windows)
    ctx.close(target)
    assert window_id not in ctx.intuition.sdl_window_id_2_window_addr_map
    assert target not in ctx.intuition.refresh_pending
    assert ctx.intuition.refresh_pending == set(windows) - {target}
    assert ctx.alloc.get_memory(target) is None
    # Creation prepends windows to the screen list. Closing its head,
    # middle or tail must preserve the remaining list and host windows.
    linked = []
    addr = ctx.screen.FirstWindow.val
    while addr:
        linked.append(addr)
        addr = WindowStruct(ctx.mem, addr).NextWindow.val
    assert linked == [addr for addr in reversed(windows) if addr != target]
    assert len(ctx.windows) == 2
    kinds = [kind for kind, _ in ctx.events]
    assert kinds[0] == "timer"
    assert kinds[-1] == "window"
    assert kinds.index("texture") < kinds.index("renderer") < kinds.index("window")
    ctx.close_all()


def intuition_close_window_queued_resize_test(ctx):
    target = ctx.open()
    other = ctx.open()
    window_id = ctx.intuition.find_sdl_window_by_amiga_addr(target)
    ctx.close(target)
    replacement = ctx.alloc.alloc_memory(WindowStruct.get_size())
    marker = bytes([0xA5]) * replacement.size
    ctx.mem.w_block(replacement.addr, marker)
    assert ctx.intuition.ingest_sdl_event(ctx, ctx.resize(window_id)) is None
    assert ctx.mem.r_block(replacement.addr, replacement.size) == marker
    # The live window must continue to receive its own events.
    other_id = ctx.intuition.find_sdl_window_by_amiga_addr(other)
    event = ctx.intuition.ingest_sdl_event(ctx, ctx.resize(other_id))
    assert event.win_addr == other
    assert WindowStruct(ctx.mem, other).Width.val == 123
    ctx.alloc.free_memory(replacement)
    ctx.close_all()


def intuition_close_window_translated_event_reused_address_test(ctx):
    target = ctx.open()
    window_id = ctx.intuition.find_sdl_window_by_amiga_addr(target)
    pending = ctx.intuition.ingest_sdl_event(ctx, ctx.resize(window_id))
    ctx.close(target)
    replacement = ctx.open()
    assert replacement == target
    assert ctx.intuition.find_sdl_window_by_amiga_addr(replacement) != window_id
    ctx.intuition.queue_idcmp = Mock()
    ctx.intuition.drain_pending_intui_events(ctx, pending)
    ctx.intuition.queue_idcmp.assert_not_called()
    ctx.close_all()


def intuition_close_window_damage_rectangles_test(ctx):
    target = ctx.open()
    window = WindowStruct(ctx.mem, target)
    raster = RastPortStruct(ctx.mem, window.RPort.val)
    layer = LayerStruct(ctx.mem, raster.Layer.val)
    rect = RectangleStruct.alloc(ctx.alloc)
    for left in [0, 20]:
        rect.MinX.val = left
        rect.MinY.val = 0
        rect.MaxX.val = left + 10
        rect.MaxY.val = 10
        ctx.graphics._or_rect_region(ctx, layer.DamageList.val, rect.get_addr())
    rect.free()
    ctx.close(target)
    ctx.close_all()


def intuition_close_window_direct_late_message_test(ctx, monkeypatch):
    target = ctx.open()
    ctx.close(target)
    read = ctx.mem.r32

    def guard(addr):
        assert not target <= addr < target + WindowStruct.get_size()
        return read(addr)

    monkeypatch.setattr(ctx.mem, "r32", guard)
    ctx.intuition.queue_idcmp(ctx, target, IDCMP_NEWSIZE)
    ctx.close_all()


def intuition_close_window_timer_race_test(ctx):
    target = ctx.open()
    window_id = ctx.intuition.find_sdl_window_by_amiga_addr(target)

    def remove(timer):
        # An event queued by a timer already in progress must be harmless.
        assert ctx.intuition.ingest_sdl_event(ctx, ctx.resize(window_id)) is None
        return ctx.remove_timer(timer)

    ctx.sdl.SDL_RemoveTimer = remove
    ctx.close(target)
    ctx.close_all()


def intuition_close_window_port_before_guest_free_test(ctx, monkeypatch):
    target = ctx.open()
    free = ctx.alloc.free_mem

    def poison(addr, size):
        free(addr, size)
        if addr == target:
            ctx.mem.clear_block(addr, size, 0xA5)

    monkeypatch.setattr(ctx.alloc, "free_mem", poison)
    ctx.close(target)
    ctx.close_all()


def intuition_close_window_cleanup_exception_test(ctx):
    target = ctx.open()

    def delete(ctx_arg, port):
        ctx.delete_port(ctx_arg, port)
        raise RuntimeError("delete port")

    ctx.exec_lib.DeleteMsgPort = delete
    with pytest.raises(RuntimeError, match="delete port"):
        ctx.close(target)
    ctx.close_all()


def intuition_close_window_timer_failure_test(ctx):
    ctx.sdl.SDL_AddTimer = Mock(return_value=0)
    ctx.open()
    ctx.close_all()
    assert not any(kind == "timer" for kind, _ in ctx.events)


def intuition_close_window_missing_host_test(ctx):
    target = ctx.open()
    window_id = ctx.intuition.find_sdl_window_by_amiga_addr(target)
    ctx.intuition.sdl_window_id_2_sdl_window.pop(window_id)
    ctx.destroy_host_window(window_id)
    ctx.close(target)
    assert [event for event in ctx.events if event == ("window", window_id)] == [
        ("window", window_id)
    ]
    ctx.close_all()


def intuition_window_unknown_id_test(ctx):
    ctx.next_window_id = 1
    target = ctx.open()
    before = ctx.mem.r_block(target, WindowStruct.get_size())
    assert ctx.intuition.ingest_sdl_event(ctx, ctx.resize(0)) is None
    assert ctx.mem.r_block(target, WindowStruct.get_size()) == before
    ctx.close_all()


def intuition_window_global_quit_test(ctx):
    windows = [ctx.open(), ctx.open()]
    ctx.intuition.queue_idcmp = Mock()
    event = SimpleNamespace(type=ctx.sdl.SDL_QUIT)
    assert ctx.intuition.ingest_sdl_event(ctx, event) is None
    assert {call.args[1] for call in ctx.intuition.queue_idcmp.call_args_list} == set(
        windows
    )
    ctx.close_all()


def intuition_close_library_with_live_windows_test(ctx):
    ctx.open()
    ctx.open()
    lib = ctx.intuition
    lib._lib_opened = True
    lib._default_title_memory = ctx.alloc.alloc_memory(10)
    lib._sdl_flags = 3
    lib.graphics_lib_addr = 0x1234
    ctx.sdl.SDL_QuitSubSystem = Mock()

    def close_graphics(addr):
        assert addr == 0x1234
        assert not ctx.windows
        assert not ctx.renderers
        assert ctx.alloc.get_memory(ctx.screen.get_addr()) is None
        ctx.font.free()

    ctx.lib_mgr = SimpleNamespace(close_lib=close_graphics)
    lib.close_lib(ctx, 0)
    assert not lib._lib_opened
    assert not ctx.windows
    assert not ctx.timers
    assert not ctx.textures
    assert not ctx.alloc.mem_objs
    assert ctx.alloc.is_all_free()
    ctx.sdl.SDL_QuitSubSystem.assert_called_once_with(3)
    if ctx.labels:
        assert not ctx.labels.get_all_labels()
