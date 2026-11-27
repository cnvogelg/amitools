import builtins
import struct
import zlib

import pytest

from amitools.vamos.display.base import Color
from amitools.vamos.display.png import PNGDisplay


def decode_png(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    offset, compressed = 8, bytearray()
    while offset < len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + size]
        crc = struct.unpack_from(">I", data, offset + 8 + size)[0]
        assert crc == zlib.crc32(kind + payload)
        if kind == b"IHDR":
            width, height, depth, color, *_ = struct.unpack(">IIBBBBB", payload)
            assert (depth, color) == (8, 6)
        if kind == b"IDAT":
            compressed.extend(payload)
        offset += size + 12
    raw = zlib.decompress(compressed)
    stride = width * 4 + 1
    assert len(raw) == stride * height
    assert all(raw[y * stride] == 0 for y in range(height))
    return (
        width,
        height,
        b"".join(raw[y * stride + 1 : (y + 1) * stride] for y in range(height)),
    )


def png_frames_resize_and_palette_test(tmp_path):
    display = PNGDisplay(tmp_path)
    a = display.create_window("a", 6, 4)
    b = display.create_window("b", 1, 1)
    palette = {n: Color(n, 255 - n, 30) for n in range(256)}
    frame = display.create_frame(a, 3, 2)
    frame.upload(bytes([0, 1, 2, 3, 4, 5]), palette)
    frame.present((2, 2))
    w, h, pixels = decode_png((tmp_path / "window-0001.png").read_bytes())
    assert (w, h) == (3, 2)  # guest resolution, not host scaling
    assert pixels[8:12] == bytes((2, 253, 30, 255))
    other = display.create_frame(b, 1, 1)
    other.upload(bytes([255]), palette)
    other.present()
    replacement = frame.replacement(1, 2)
    palette[1] = Color(50, 60, 70)
    replacement.upload(bytes([1, 1]), palette)
    replacement.present()
    assert decode_png((tmp_path / "window-0001.png").read_bytes()) == (
        1,
        2,
        bytes((50, 60, 70, 255)) * 2,
    )
    assert decode_png((tmp_path / "window-0002.png").read_bytes())[:2] == (1, 1)
    assert display.poll() == []
    assert [e.window_id for e in display.poll(20)] == [a.id, b.id]
    assert display.poll(20) == []
    assert len(list(tmp_path.iterdir())) == 2


def png_write_failure_preserves_previous_frame_test(tmp_path, monkeypatch):
    display = PNGDisplay(tmp_path)
    frame = display.create_frame(display.create_window("a", 1, 1), 1, 1)
    frame.present()
    old = (tmp_path / "window-0001.png").read_bytes()

    def fail(*args):
        raise OSError("replace failed")

    monkeypatch.setattr("amitools.vamos.display.png.os.replace", fail)
    with pytest.raises(OSError, match="replace failed"):
        frame.present()
    assert (tmp_path / "window-0001.png").read_bytes() == old
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize("wait_for_close", [True, False])
def png_native_window_idle_capture_test(tmp_path, monkeypatch, wait_for_close):
    # Fail even a lazy SDL/TTF import: this must work without those packages.
    original = builtins.__import__

    def no_sdl(name, *args, **kwargs):
        if name == "sdl2" or name.startswith("sdl2."):
            raise AssertionError("PNG backend imported SDL")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_sdl)
    from amitools.fd import read_lib_fd
    from amitools.vamos.lib.intuition import (
        IDCMP_CLOSEWINDOW,
        WA_IDCMP,
        WA_Height,
        WA_Width,
        WindowStruct,
    )
    from amitools.vamos.libmgr import SetupLibManager
    from amitools.vamos.libtypes import MsgPort
    from amitools.vamos.machine import (
        REG_A0,
        REG_A1,
        REG_A6,
        REG_D0,
        REG_D1,
        REG_D2,
        REG_D3,
        Code,
        Machine,
        MemoryMap,
        Runtime,
    )
    from amitools.vamos.path import PathManager
    from amitools.vamos.schedule import Scheduler
    from amitools.vamos.task import ExecTask

    machine = Machine()
    memory = MemoryMap(machine)
    memory.setup_ram_allocator()
    scheduler = Scheduler(machine)
    runtime = Runtime(machine)

    def runner(code, name=None):
        task = scheduler.get_cur_task()
        return task.sub_run(code, name) if task else runtime.run(code, name)

    manager = SetupLibManager(
        machine,
        memory,
        runner,
        scheduler,
        PathManager(),
        display_backend="png",
        display_output=str(tmp_path),
    )
    manager.setup()
    manager.open_base_libs()
    ctx = manager.exec_ctx
    library = manager.lib_mgr.open_lib("intuition.library")
    intuition = manager.lib_mgr.get_vlib_by_addr(library).get_impl()
    block = ctx.alloc.alloc_memory(64)
    code = ctx.alloc.alloc_memory(6)
    for n, (tag, value) in enumerate(
        ((WA_Width, 20), (WA_Height, 12), (WA_IDCMP, IDCMP_CLOSEWINDOW), (0, 0))
    ):
        ctx.mem.w32(block.addr + n * 8, tag)
        ctx.mem.w32(block.addr + n * 8 + 4, value)
    bias = (
        read_lib_fd("intuition.library")
        .get_func_by_name("OpenWindowTagList")
        .get_bias()
    )
    ctx.mem.w_block(code.addr, struct.pack(">HHH", 0x4EAE, (-bias) & 65535, 0x4E75))

    def run(task):
        result = task.sub_run(
            Code(
                code.addr,
                set_regs={REG_A6: library, REG_A0: 0, REG_A1: block.addr},
                get_regs=[REG_D0],
            )
        )
        assert result.mach_error is None
        address = result.regs[REG_D0]
        window = WindowStruct(ctx.mem, address)
        graphics = intuition.graphics_lib
        ctx.cpu.w_reg(REG_A1, window.RPort.val)
        ctx.cpu.w_reg(REG_D0, 2)
        graphics.SetAPen(ctx)
        for register, value in ((REG_D0, 2), (REG_D1, 3), (REG_D2, 5), (REG_D3, 7)):
            ctx.cpu.w_reg(register, value)
        graphics.RectFill(ctx)
        if wait_for_close:
            messages = ctx.exec_lib
            port = MsgPort(ctx.mem, window.UserPort.val)
            messages.wait_port(port)
            message = messages.get_msg(port)
            assert ctx.mem.r32(message.addr + 20) == IDCMP_CLOSEWINDOW
            messages.reply_msg(message)
        ctx.cpu.w_reg(REG_A0, address)
        intuition.CloseWindow(ctx)
        return 0

    task = ExecTask(machine, ctx.alloc, "PNG capture", func=run)
    scheduler.add_task(task.get_sched_task())
    assert scheduler.schedule()
    assert task.get_sched_task().get_exit_code() == 0
    assert not scheduler.after_schedule_callbacks and not scheduler.idle_callbacks
    width, height, pixels = decode_png((tmp_path / "window-0001.png").read_bytes())
    assert (width, height) == (20, 12)
    assert pixels[(3 * width + 2) * 4 : (3 * width + 3) * 4] == bytes(
        (255, 255, 255, 255)
    )
    assert pixels[:4] == bytes((168, 168, 168, 255))
    task.free()
    ctx.alloc.free_memory(code)
    ctx.alloc.free_memory(block)
    manager.lib_mgr.close_lib(library)
    manager.close_base_libs()
    manager.cleanup()
    assert ctx.alloc.is_all_free()
    machine.cleanup()
