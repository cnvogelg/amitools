from types import SimpleNamespace

import pytest

from amitools.vamos.lib.GadToolsLibrary import GadToolsLibrary
from amitools.vamos.lib.graphics import BitMapStruct, RastPortStruct
from amitools.vamos.lib.GraphicsLibrary import GraphicsLibrary
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc


@pytest.mark.parametrize("recessed", [False, True])
def gadtools_bevel_visual_pens_and_cleanup_test(recessed):
    ctx = SimpleNamespace(mem=MockMemory())
    ctx.alloc = MemoryAlloc(ctx.mem)
    port = RastPortStruct.alloc(ctx.alloc)
    bitmap = BitMapStruct.alloc(ctx.alloc)
    bitmap.Depth.val = 3
    port.BitMap.val = bitmap.addr
    commands = []
    graphics = GraphicsLibrary()
    graphics.get_rp_graphics = lambda rp: SimpleNamespace(
        batch=SimpleNamespace(add=commands.append)
    )
    block = ctx.alloc.alloc_memory(64)
    draw, pens, tags = block.addr, block.addr + 16, block.addr + 32
    ctx.mem.w32(draw + 4, pens)
    ctx.mem.w16(pens + 6, 7)
    ctx.mem.w16(pens + 8, 3)
    released = []
    ctx.exec_lib = SimpleNamespace(
        graphics_lib=graphics,
        intuition_lib=SimpleNamespace(
            GetScreenDrawInfo=lambda *args: draw,
            FreeScreenDrawInfo=lambda *args: released.append(args),
        ),
    )
    lib = GadToolsLibrary()
    lib.setup_lib(ctx, 0)
    before = ctx.alloc.get_free_bytes()
    assert lib.GetVisualInfoA(ctx, 0, 0) == 0
    visual = lib.GetVisualInfoA(ctx, 0x400, 0)
    ctx.mem.w32(tags, 0x80080034)
    ctx.mem.w32(tags + 4, visual)
    ctx.mem.w32(tags + 8, 0x80080033)
    ctx.mem.w32(tags + 12, int(recessed))
    saved = bytes(ctx.mem.r_block(port.addr, port.get_size()))
    lib.DrawBevelBoxA(ctx, port.addr, 2, 3, 10, 8, tags)
    assert [command.state.foreground for command in commands] == (
        [3, 3, 7, 7] if recessed else [7, 7, 3, 3]
    )
    assert len(released) == 1
    assert bytes(ctx.mem.r_block(port.addr, port.get_size())) == saved
    lib.FreeVisualInfo(ctx, visual)
    lib.FreeVisualInfo(ctx, visual)
    assert ctx.alloc.get_free_bytes() == before
    lib.GetVisualInfoA(ctx, 0x400, 0)
    lib.finish_lib(ctx)
    assert ctx.alloc.get_free_bytes() == before
    ctx.alloc.free_memory(block)
    port.free()
    bitmap.free()
    assert ctx.alloc.is_all_free()
