"""GadTools visual information and bevel rendering for classic clients."""

from dataclasses import replace

from amitools.vamos.lib.graphics import RastPortStruct
from amitools.vamos.lib.GraphicsLibrary import BFDraw
from amitools.vamos.libcore.impl import LibImpl
from amitools.vamos.libtypes import TagList


class GadToolsLibrary(LibImpl):
    def setup_lib(self, ctx, base_addr):
        self.visuals = {}

    def GetVisualInfoA(self, ctx, screen, taglist):
        if not screen:
            return 0
        block = ctx.alloc.alloc_memory(
            4, label="GadTools VisualInfo", except_on_failure=False
        )
        if block is None:
            return 0
        ctx.mem.w32(block.addr, screen)
        self.visuals[block.addr] = block
        return block.addr

    def FreeVisualInfo(self, ctx, vi):
        block = self.visuals.pop(vi, None)
        if block:
            ctx.alloc.free_memory(block)

    def finish_lib(self, ctx):
        for address in tuple(self.visuals):
            self.FreeVisualInfo(ctx, address)

    def DrawBevelBoxA(self, ctx, rport, left, top, width, height, taglist):
        tags = (
            {tag.tag.val: tag.data.val for tag in TagList(ctx.mem, taglist)}
            if taglist
            else {}
        )
        left, top, width, height = [
            ((v + 32768) & 65535) - 32768 for v in (left, top, width, height)
        ]
        if width <= 0 or height <= 0:
            return
        graphics = ctx.exec_lib.graphics_lib
        backing = graphics.get_rp_graphics(rport)
        if backing is None:
            return
        state = graphics._raster_state(ctx, RastPortStruct(ctx.mem, rport))
        if state is None:
            return
        # GTBB_Recessed = GT_TagBase + 51. Default screen shine/shadow pens.
        shine, shadow = 2, 1
        visual = self.visuals.get(tags.get(0x80080034))  # GT_VisualInfo
        if visual is not None:
            screen = ctx.mem.r32(visual.addr)
            intuition = ctx.exec_lib.intuition_lib
            draw = intuition.GetScreenDrawInfo(ctx, screen)
            if draw:
                try:
                    pens = ctx.mem.r32(draw + 4)
                    shine, shadow = ctx.mem.r16(pens + 6), ctx.mem.r16(pens + 8)
                finally:
                    intuition.FreeScreenDrawInfo(ctx, screen, draw)
        if tags.get(0x80080033):
            shine, shadow = shadow, shine
        x2, y2 = left + width - 1, top + height - 1
        for x, y, xx, yy, pen in (
            (left, top, x2, top, shine),
            (left, top, left, y2, shine),
            (x2, top, x2, y2, shadow),
            (left, y2, x2, y2, shadow),
        ):
            backing.batch.add(
                BFDraw(
                    x,
                    y,
                    xx,
                    yy,
                    None,
                    0,
                    replace(state, foreground=pen, mode=0, pattern=65535),
                )
            )
