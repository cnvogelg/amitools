"""Opt-in native SDL test: AMITOOLS_TEST_SDL=1 with PySDL2 and SDL_ttf."""

import ctypes
import os

import pytest


@pytest.mark.skipif(
    os.environ.get("AMITOOLS_TEST_SDL") != "1", reason="native SDL opt-in"
)
def graphics_native_sdl_window_and_render_test(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    import sdl2
    from amitools.fd import read_lib_fd
    from amitools.vamos.lib.graphics import RastPortStruct
    from amitools.vamos.lib.intuition import WA_Width, WA_Height, WindowStruct
    from amitools.vamos.libmgr import SetupLibManager
    from amitools.vamos.machine import Machine, MemoryMap, Runtime, Code
    from amitools.vamos.machine import (
        REG_A0,
        REG_A1,
        REG_A6,
        REG_D0,
        REG_D1,
        REG_D2,
        REG_D3,
    )
    from amitools.vamos.path import PathManager
    from amitools.vamos.schedule import Scheduler
    from amitools.vamos.task import ExecTask

    machine = Machine()
    runtime = Runtime(machine)
    memory_map = MemoryMap(machine)
    memory_map.setup_ram_allocator()
    scheduler = Scheduler(machine)
    manager = SetupLibManager(
        machine, memory_map, runtime.run, scheduler, PathManager()
    )
    manager.setup()
    manager.open_base_libs()
    ctx = manager.exec_ctx
    task = ExecTask(machine, ctx.alloc, "SDL native caller", func=lambda task: 0)
    task.get_sched_task().config(scheduler, 1000)
    ctx.task = task
    block = ctx.alloc.alloc_memory(64)
    code = ctx.alloc.alloc_memory(6)
    library = 0
    window = 0
    try:
        library = manager.lib_mgr.open_lib("intuition.library")
        intuition = manager.lib_mgr.get_vlib_by_addr(library).get_impl()
        assert intuition._lib_opened
        graphics = intuition.graphics_lib
        for index, (tag, data) in enumerate([(WA_Width, 64), (WA_Height, 32), (0, 0)]):
            ctx.mem.w32(block.addr + 8 * index, tag)
            ctx.mem.w32(block.addr + 8 * index + 4, data)
        bias = (
            read_lib_fd("intuition.library")
            .get_func_by_name("OpenWindowTagList")
            .get_bias()
        )
        ctx.mem.w16(code.addr, 0x4EAE)
        ctx.mem.w16(code.addr + 2, -bias & 0xFFFF)
        ctx.mem.w16(code.addr + 4, 0x4E75)
        result = runtime.start(
            Code(
                code.addr,
                machine.get_scratch_top(),
                set_regs={REG_A6: library, REG_A0: 0, REG_A1: block.addr},
            )
        )
        assert result.exit
        window = ctx.cpu.r_reg(REG_D0)
        assert window
        rp = RastPortStruct(ctx.mem, WindowStruct(ctx.mem, window).RPort.val)
        backing = graphics.get_rp_graphics(rp.addr)
        ctx.cpu.w_reg(REG_A1, rp.addr)
        ctx.cpu.w_reg(REG_D0, 2)
        graphics.SetAPen(ctx)
        for reg, value in ((REG_D0, 2), (REG_D1, 2), (REG_D2, 10), (REG_D3, 10)):
            ctx.cpu.w_reg(reg, value)
        graphics.RectFill(ctx)
        ctx.cpu.w_reg(REG_D0, 1)
        graphics.SetAPen(ctx)
        ctx.cpu.w_reg(REG_D0, 2)
        ctx.cpu.w_reg(REG_D1, 5)
        graphics.Move(ctx)
        ctx.cpu.w_reg(REG_D0, 10)
        graphics.Draw(ctx)
        ctx.mem.w_block(block.addr, b"HiEXTRA")
        ctx.cpu.w_reg(REG_A0, block.addr)
        ctx.cpu.w_reg(REG_D0, 2)
        graphics.Text(ctx)
        assert backing.batch.texts[0].string == "Hi"
        assert rp.cp_y.val == 5 and rp.cp_x.val > 10
        intuition._flush_batch(backing)
        pixels = (ctypes.c_uint32 * (64 * 32))()
        assert sdl2.SDL_SetRenderTarget(backing.renderer, backing.texture) == 0
        try:
            assert (
                sdl2.SDL_RenderReadPixels(
                    backing.renderer,
                    None,
                    sdl2.SDL_PIXELFORMAT_RGBA8888,
                    pixels,
                    64 * 4,
                )
                == 0
            )
        finally:
            sdl2.SDL_SetRenderTarget(backing.renderer, None)
        assert pixels[9 * 64 + 5] == 0xFFFFFFFF
        assert pixels[5 * 64 + 5] == 0x000000FF
        from amitools.vamos.lib.graphics import LayerStruct

        damage = LayerStruct(ctx.mem, rp.Layer.val).DamageList.val
        assert graphics._replace_region(ctx, damage, [(2, 9, 3, 9), (7, 9, 8, 9)])
        ctx.cpu.w_reg(REG_A0, window)
        intuition.BeginRefresh(ctx)
        ctx.cpu.w_reg(REG_A1, rp.addr)
        ctx.cpu.w_reg(REG_D0, 1)
        graphics.SetAPen(ctx)
        for reg, value in ((REG_D0, 0), (REG_D1, 0), (REG_D2, 63), (REG_D3, 31)):
            ctx.cpu.w_reg(reg, value)
        graphics.RectFill(ctx)
        ctx.cpu.w_reg(REG_A0, window)
        ctx.cpu.w_reg(REG_D0, 1)
        intuition.EndRefresh(ctx)
        sdl2.SDL_SetRenderTarget(backing.renderer, backing.texture)
        try:
            assert (
                sdl2.SDL_RenderReadPixels(
                    backing.renderer,
                    None,
                    sdl2.SDL_PIXELFORMAT_RGBA8888,
                    pixels,
                    64 * 4,
                )
                == 0
            )
        finally:
            sdl2.SDL_SetRenderTarget(backing.renderer, None)
        assert pixels[9 * 64 + 2] == pixels[9 * 64 + 8] == 0x000000FF
        assert pixels[9 * 64 + 5] == 0xFFFFFFFF
        ctx.cpu.w_reg(REG_A1, rp.addr)
        ctx.cpu.w_reg(REG_D0, 2)
        graphics.SetAPen(ctx)
        for reg, value in zip((REG_D0, REG_D1, REG_D2, REG_D3), (20, 20, 21, 21)):
            ctx.cpu.w_reg(reg, value)
        graphics.RectFill(ctx)
        rp.Mask.val = 3
        ctx.cpu.w_reg(REG_D0, 2)
        graphics.SetDrMd(ctx)
        for reg, value in zip((REG_D0, REG_D1, REG_D2, REG_D3), (20, 20, 21, 21)):
            ctx.cpu.w_reg(reg, value)
        graphics.RectFill(ctx)
        intuition._flush_batch(backing)
        assert backing.surface.pixels[20 * 64 + 20] == 1  # white pen 2 XOR mask 3
        state = graphics._raster_state(ctx, rp)
        offset, bit = 20 * state.stride + 20 // 8, 0x80 >> (20 & 7)
        assert [bool(ctx.mem.r8(addr + offset) & bit) for addr in state.planes] == [
            True,
            False,
            False,
        ]
        ctx.cpu.w_reg(REG_D0, 1)
        graphics.SetDrMd(ctx)
        rp.Mask.val = 7
        from amitools.vamos.machine import REG_D4, REG_D5

        for dx, dy in [(2, 0), (-2, 0), (0, 2), (0, -2), (100, 0), (0, 0)]:
            ctx.cpu.w_reg(REG_A1, rp.addr)
            for pen, rect in [(0, (0, 0, 63, 31)), (2, (4, 4, 8, 8))]:
                ctx.cpu.w_reg(REG_D0, pen)
                graphics.SetAPen(ctx)
                for reg, value in zip((REG_D0, REG_D1, REG_D2, REG_D3), rect):
                    ctx.cpu.w_reg(reg, value)
                graphics.RectFill(ctx)
            intuition._flush_batch(backing)
            for reg, value in (
                (REG_A1, window),
                (REG_D0, dx & 0xFFFF),
                (REG_D1, dy & 0xFFFF),
                (REG_D2, 0),
                (REG_D3, 0),
                (REG_D4, 63),
                (REG_D5, 31),
            ):
                ctx.cpu.w_reg(reg, value)
            intuition.ScrollWindowRaster(ctx)
            sdl2.SDL_SetRenderTarget(backing.renderer, backing.texture)
            try:
                assert (
                    sdl2.SDL_RenderReadPixels(
                        backing.renderer,
                        None,
                        sdl2.SDL_PIXELFORMAT_RGBA8888,
                        pixels,
                        64 * 4,
                    )
                    == 0
                )
            finally:
                sdl2.SDL_SetRenderTarget(backing.renderer, None)
            if dx == 100:
                assert all(pixel == 0xA8A8A8FF for pixel in pixels)
            else:
                assert pixels[(6 - dy) * 64 + 6 - dx] == 0xFFFFFFFF
        ctx.cpu.w_reg(REG_A0, window)
        intuition.CloseWindow(ctx)
        window = 0
        manager.lib_mgr.close_lib(library)
        library = 0
        # Font, screen, SDL and ownership state must rebuild after close.
        library = manager.lib_mgr.open_lib("intuition.library")
        assert manager.lib_mgr.get_vlib_by_addr(library).get_impl()._lib_opened
    finally:
        if window:
            ctx.cpu.w_reg(REG_A0, window)
            intuition.CloseWindow(ctx)
        if library:
            manager.lib_mgr.close_lib(library)
        ctx.alloc.free_memory(code)
        ctx.alloc.free_memory(block)
        ctx.task = None
        task.free()
        manager.close_base_libs()
        manager.cleanup()
        assert ctx.alloc.is_all_free()
        machine.cleanup()
