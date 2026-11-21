from types import SimpleNamespace

from amitools.vamos.display.base import Event
from amitools.vamos.lib.intuition_gadgets import chain

from amitools.vamos.lib.intuition import WindowStruct
from amitools.vamos.lib.IntuitionLibrary import IntuitionLibrary
from amitools.vamos.machine.mock import MockMemory


def gadgets_link_remove_and_verify_test():
    ctx = SimpleNamespace(mem=MockMemory())
    lib = IntuitionLibrary()
    window = WindowStruct(ctx.mem, 0x400)
    window.Width.val, window.Height.val = 200, 100
    a, b = 0x800, 0x900
    ctx.mem.w32(a, b)
    assert lib.AddGList(ctx, window.addr, a, 65535, 65535, 0) == 0
    assert list(chain(ctx.mem, window.FirstGadget.val)) == [a, b]
    assert lib.AddGList(ctx, window.addr, a, 0, 1, 0) == 65535
    for offset, value in ((4, 10), (6, 10), (8, 30), (10, 10), (14, 1), (16, 1)):
        ctx.mem.w16(b + offset, value)
    messages = []
    lib.queue_idcmp = lambda *args, **kwargs: messages.append((args, kwargs))
    lib._window_scales[1] = (2, 2)
    assert lib._gadget_event(ctx, Event("button_down", 1, 40, 30, 1), window.addr)
    assert lib._gadget_event(ctx, Event("button_up", 1, 40, 30, 1), window.addr)
    assert messages[0][0][2] == 0x40
    assert messages[0][1]["iaddress"] == b
    assert lib.RemoveGList(ctx, window.addr, a, 1) == 0
    assert window.FirstGadget.val == b
    assert lib.RemoveGList(ctx, window.addr, b, 65535) == 0
    assert window.FirstGadget.val == 0


def custom_gadget_restores_rastport_test(monkeypatch):
    from amitools.vamos.lib import boopsi
    from amitools.vamos.lib.graphics import RastPortStruct
    from amitools.vamos.mem import MemoryAlloc

    ctx = SimpleNamespace(mem=MockMemory())
    ctx.alloc = MemoryAlloc(ctx.mem)
    window = WindowStruct.alloc(ctx.alloc)
    port = RastPortStruct.alloc(ctx.alloc)
    gadget = ctx.alloc.alloc_memory(44)
    window.RPort.val = port.addr
    ctx.mem.w32(gadget.addr + 30, 0x1234)
    port.AreaPtrn.val = 0
    port.FgPen.val = 2
    saved = bytes(ctx.mem.r_block(port.addr, RastPortStruct.get_size()))
    lib = IntuitionLibrary()
    lib.GetScreenDrawInfo = lambda *args: 0
    lib.FreeScreenDrawInfo = lambda *args: None

    def render(ctx, hook, obj, message):
        port.AreaPtrn.val = 0x800
        port.FgPen.val = 3

    monkeypatch.setattr(boopsi, "call_hook", render)
    before = ctx.alloc.get_free_bytes()
    lib._custom_render(ctx, window.addr, gadget.addr)
    assert bytes(ctx.mem.r_block(port.addr, RastPortStruct.get_size())) == saved
    assert ctx.alloc.get_free_bytes() == before
    ctx.alloc.free_memory(gadget)
    port.free()
    window.free()
    assert ctx.alloc.is_all_free()


def custom_gadget_input_lifecycle_test(monkeypatch):
    from amitools.vamos.lib import boopsi
    from amitools.vamos.mem import MemoryAlloc

    ctx = SimpleNamespace(mem=MockMemory())
    ctx.alloc = MemoryAlloc(ctx.mem)
    window = WindowStruct.alloc(ctx.alloc)
    gadget = ctx.alloc.alloc_memory(44)
    window.Width.val, window.Height.val = 100, 100
    window.FirstGadget.val = gadget.addr
    for offset, value in ((4, 10), (6, 20), (8, 30), (10, 10), (16, 5)):
        ctx.mem.w16(gadget.addr + offset, value)
    ctx.mem.w32(gadget.addr + 30, 0x1234)
    lib = IntuitionLibrary()
    lib._window_scales[1] = (2, 2)
    lib.GetScreenDrawInfo = lambda *args: 0
    lib.FreeScreenDrawInfo = lambda *args: None
    calls, messages = [], []
    lib.queue_idcmp = lambda *args, **kwargs: messages.append((args, kwargs))

    def hook(ctx, hook, obj, message):
        method = ctx.mem.r32(message)
        calls.append(method)
        info = ctx.mem.r32(message + 4)
        assert ctx.mem.r32(info + 4) == window.addr
        assert obj == gadget.addr
        if method == 0:
            assert ctx.mem.r16(message + 8) == 5
            assert ctx.mem.r16(message + 10) == 5
            return 4
        if method in (2, 3):
            event = ctx.mem.r32(message + 8)
            assert ctx.mem.r8(event + 4) == 2
            assert ctx.mem.r16(event + 6) == (0x68 if method == 2 else 0xE8)
            assert ctx.mem.r16(message + 16) == 5
            assert ctx.mem.r16(message + 18) == 5
            if method == 3:
                ctx.mem.w32(ctx.mem.r32(message + 12), 123)
                return 10  # GMR_NOREUSE | GMR_VERIFY
        if method == 4:
            assert ctx.mem.r32(message + 8) == 0
        return 0

    monkeypatch.setattr(boopsi, "call_hook", hook)
    before = ctx.alloc.get_free_bytes()
    assert lib._gadget_event(ctx, Event("button_down", 1, 30, 50, 1), window.addr)
    assert lib._active_gadget == (window.addr, gadget.addr)
    assert lib._gadget_event(ctx, Event("button_up", 1, 30, 50, 1), window.addr)
    assert lib._active_gadget == (None, None)
    assert calls == [0, 2, 3, 4]
    assert messages[0][0][2] == 0x40
    assert messages[0][1] == {"code": 123, "iaddress": gadget.addr}
    assert ctx.alloc.get_free_bytes() == before
    ctx.alloc.free_memory(gadget)
    window.free()
    assert ctx.alloc.is_all_free()


def custom_gadget_native_dispatch_test():
    from amitools.vamos.machine import Code, Machine, Runtime
    from amitools.vamos.mem import MemoryAlloc

    machine = Machine()
    runtime = Runtime(machine)
    ctx = SimpleNamespace(
        mem=machine.mem,
        cpu=machine.cpu,
        alloc=MemoryAlloc.for_machine(machine),
        runner=runtime.run,
    )
    window = WindowStruct.alloc(ctx.alloc)
    gadget = ctx.alloc.alloc_memory(44)
    block = ctx.alloc.alloc_memory(80)
    lib = IntuitionLibrary()
    lib.GetScreenDrawInfo = lambda *args: 0
    lib.FreeScreenDrawInfo = lambda *args: None
    # Native hook: hit test returns GMR_GADGETHIT; HANDLEINPUT writes
    # termination code 123 and returns GMR_NOREUSE | GMR_VERIFY.
    ctx.mem.w_block(
        block.addr,
        bytes.fromhex(
            "20110c8000000000660470044e75"
            "0c8000000003660e2069000c20bc0000007b700a4e75"
            "70004e75"
        ),
    )
    hook = block.addr + 60
    ctx.mem.w32(hook + 8, block.addr)
    ctx.mem.w32(gadget.addr + 30, hook)
    ctx.mem.w16(gadget.addr + 16, 5)

    def run(opcode, address):
        assert lib._custom_method(ctx, window.addr, gadget.addr, 0) == (4, 0)
        assert lib._custom_method(ctx, window.addr, gadget.addr, 2) == (0, 0)
        assert lib._custom_method(ctx, window.addr, gadget.addr, 4) == (0, 0)
        assert lib._custom_method(
            ctx, window.addr, gadget.addr, 3, Event("button_up", 1, 0, 0, 1)
        ) == (10, 123)

    trap = machine.setup_quick_trap(run)
    try:
        result = runtime.run(Code(trap, machine.get_scratch_top()))
        assert result.mach_error is None
    finally:
        ctx.alloc.free_memory(block)
        ctx.alloc.free_memory(gadget)
        window.free()
        assert ctx.alloc.is_all_free()
        machine.cleanup()


def classic_gadget_followmouse_and_remove_test():
    ctx = SimpleNamespace(mem=MockMemory())
    lib = IntuitionLibrary()
    window = WindowStruct(ctx.mem, 0x400)
    window.FirstGadget.val = 0x800
    ctx.mem.w16(0x800 + 14, 8)
    ctx.mem.w16(0x800 + 16, 1)
    lib._active_gadget = (window.addr, 0x800)
    assert lib._reports_mouse(ctx, window.addr)
    assert not lib._reports_mouse(ctx, 0x500)
    lib.RemoveGList(ctx, window.addr, 0x800, 1)
    assert lib._active_gadget == (None, None)
    assert not lib._reports_mouse(ctx, window.addr)


def custom_gadget_raw_keys_and_reuse_test(monkeypatch):
    from amitools.vamos.lib import boopsi
    from amitools.vamos.mem import MemoryAlloc

    ctx = SimpleNamespace(mem=MockMemory())
    ctx.alloc = MemoryAlloc(ctx.mem)
    window = WindowStruct.alloc(ctx.alloc)
    gadget = ctx.alloc.alloc_memory(44)
    ctx.mem.w32(gadget.addr + 30, 0x1234)
    ctx.mem.w16(gadget.addr + 16, 5)
    lib = IntuitionLibrary()
    lib.GetScreenDrawInfo = lambda *args: 0
    lib.FreeScreenDrawInfo = lambda *args: None
    received = []

    def hook(ctx, hook, obj, message):
        method = ctx.mem.r32(message)
        if method == 3:
            event = ctx.mem.r32(message + 8)
            assert ctx.mem.r8(event + 4) == 1
            received.append((ctx.mem.r16(event + 6), ctx.mem.r16(event + 8)))
            return 4  # GMR_REUSE, no verification.
        assert method == 4
        return 0

    monkeypatch.setattr(boopsi, "call_hook", hook)
    for code in (0x20, 0xA0):
        lib._active_gadget = (window.addr, gadget.addr)
        assert not lib._custom_input(
            ctx, window.addr, gadget.addr, 3, Event("key", 1, raw_key=(False, code, 1))
        )
        assert lib._active_gadget == (None, None)
    assert received == [(0x20, 1), (0xA0, 1)]
    ctx.alloc.free_memory(gadget)
    window.free()
    assert ctx.alloc.is_all_free()
