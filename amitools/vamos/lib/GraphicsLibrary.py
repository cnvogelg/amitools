import os
import ctypes
import time
from contextlib import ExitStack

from amitools.vamos.libcore.impl import LibImpl
from amitools.vamos.machine.regs import REG_A0, REG_D0, REG_A1, REG_D1, REG_D2, REG_D3
from amitools.vamos.lib.graphics import TextAttrStruct, BitMapStruct, RastPortStruct, RegionRectangleStruct, RegionStruct, RectangleStruct, LayerStruct, JAM2
from amitools.vamos.lib.intuition import TextFontStruct, WindowStruct
from amitools.vamos.log import log_main, log_gfx
from dataclasses import dataclass

class GraphicsLibrary(LibImpl):
    def __init__(self):
        super().__init__()
        self.alloc = None
        self.fontsPath = None
        self.text_attr = None
        self.font_registry = {}
        self.topaz_font = None
        self.rp_graphics_map = {}
        self._rastport_resources = {}
        self.palette = None
        self._lib_opened = False
        self._setup_resources = None

    # ---------------------------------------------------------------------
    # Library setup / teardown
    # ---------------------------------------------------------------------

    def setup_lib(self, ctx, base_addr):
        self.alloc = ctx.alloc
        ctx.exec_lib.graphics_lib = self

    def open_lib(self, ctx, open_cnt):
        if self._lib_opened:
            return
        try:
            from sdl2 import sdlttf
        except ImportError:
            return
        if sdlttf.TTF_Init() != 0:
            log_main.error("TTF_Init failed")
            return
        try:
            with ExitStack() as rollback:
                rollback.callback(sdlttf.TTF_Quit)
                self.fontsPath = ctx.path_mgr.ami_to_sys_path(None, "FONTS:")
                if self.fontsPath is None:
                    self.fontsPath = os.path.join(os.path.dirname(__file__), "fonts")
                attr_memory = ctx.alloc.alloc_memory(
                    TextAttrStruct.get_size(), label="Graphics default TextAttr",
                    except_on_failure=False,
                )
                if attr_memory is None:
                    return
                rollback.callback(ctx.alloc.free_memory, attr_memory)
                ctx.mem.clear_block(attr_memory.addr, attr_memory.size, 0)
                attr = TextAttrStruct(ctx.mem, attr_memory.addr)
                name = "Topaz_a1200_v1.0.ttf"
                name_memory = ctx.alloc.alloc_memory(
                    len(name) + 1, label="Graphics default name",
                    except_on_failure=False,
                )
                if name_memory is None:
                    return
                rollback.callback(ctx.alloc.free_memory, name_memory)
                ctx.mem.w_cstr(name_memory.addr, name)
                attr.ta_Name.set(name_memory.addr)
                attr.ta_YSize.val = 8
                font_addr = self._open_font(ctx, attr.addr)
                if not font_addr:
                    return
                rollback.callback(self._close_font, ctx, font_addr)
                palette = create_amiga_palette()
                self.text_attr, self.topaz_font = attr, font_addr
                self.palette = palette
                self._setup_resources = rollback.pop_all()
                self._lib_opened = True
        finally:
            if not self._lib_opened:
                self.fontsPath = None

    def close_lib(self, ctx, open_cnt):
        if open_cnt or not self._lib_opened:
            return
        resources = self._setup_resources
        default_font = self.topaz_font
        self._setup_resources = None
        self.text_attr = self.topaz_font = self.palette = None
        self.fontsPath = None
        self._lib_opened = False
        with ExitStack() as cleanup:
            cleanup.callback(resources.close)
            for font_addr in tuple(self.font_registry):
                if font_addr != default_font:
                    cleanup.callback(self._close_font, ctx, font_addr)
            for rp_addr in tuple(self.rp_graphics_map):
                if rp_addr not in self._rastport_resources:
                    cleanup.callback(self.free_rast_port_graphics, ctx, rp_addr)
            for rp_addr in tuple(self._rastport_resources):
                cleanup.callback(self.free_RastPortStruct, ctx, rp_addr)

    # ---------------------------------------------------------------------
    # Canonical initializers
    # ---------------------------------------------------------------------

    def init_bitmap_canonical(self, ctx, bm_addr, width, height, depth=2):
        """Initialize a bitmap, rolling back partially allocated planes."""
        if not (0 < width <= 32767 and 0 < height <= 32767 and 1 <= depth <= 8):
            return False
        bm = BitMapStruct(ctx.mem, bm_addr)
        ctx.mem.clear_block(bm_addr, BitMapStruct.get_size(), 0)
        bm.BytesPerRow.val = ((width + 15) // 16) * 2
        bm.Rows.val = height
        bm.Depth.val = depth
        plane_size = bm.BytesPerRow.val * height
        with ExitStack() as rollback:
            for i in range(depth):
                addr = ctx.alloc.alloc_mem(plane_size, except_on_fail=False)
                if not addr:
                    ctx.mem.clear_block(bm_addr, BitMapStruct.get_size(), 0)
                    return False
                rollback.callback(ctx.alloc.free_mem, addr, plane_size)
                ctx.mem.clear_block(addr, plane_size, 0)
                bm.Planes[i].val = addr
            rollback.pop_all()
        return True

    def init_rastport_canonical(self, ctx, rp_addr):
        """Reset the complete public RastPort, then apply system defaults."""
        ctx.mem.clear_block(rp_addr, RastPortStruct.get_size(), 0)
        rp = RastPortStruct(ctx.mem, rp_addr)

        rp.FgPen.set(-1)
        rp.AOlPen.set(-1)
        rp.Mask.set(0xFF)

        rp.DrawMode.set(JAM2)
        rp.LinePtrn.set(0xFFFF)

        self._set_font(ctx, rp_addr, self.topaz_font)

    # ---------------------------------------------------------------------
    # Unified RastPort + BitMap creation helpers
    # ---------------------------------------------------------------------

    def create_window_rastport(self, ctx, sdl_win, width, height, depth=2):
        with ExitStack() as rollback:
            objects = []
            for struct in (BitMapStruct, LayerStruct, RastPortStruct):
                memory = ctx.alloc.alloc_memory(
                    struct.get_size(), label=struct.__name__, except_on_failure=False
                )
                if memory is None:
                    return 0, 0, 0
                rollback.callback(ctx.alloc.free_memory, memory)
                ctx.mem.clear_block(memory.addr, memory.size, 0)
                objects.append(struct(ctx.mem, memory.addr))
            bm, layer, rp = objects
            if not self.init_bitmap_canonical(ctx, bm.addr, width, height, depth):
                return 0, 0, 0
            plane_size = bm.BytesPerRow.val * bm.Rows.val
            for i in range(depth):
                rollback.callback(ctx.alloc.free_mem, bm.Planes[i].val, plane_size)
            damage = self._new_region(ctx)
            if not damage:
                return 0, 0, 0
            rollback.callback(self._dispose_region, ctx, damage)
            layer.Width.val, layer.Height.val = width, height
            layer.DamageList.val = damage
            self.init_rastport_canonical(ctx, rp.addr)
            rp.FgPen.val, rp.AOlPen.val = 1, 0
            rp.cp_y.val = rp.TxBaseline.val
            rp.BitMap.val, rp.Layer.val = bm.addr, layer.addr
            layer.rp.val = rp.addr
            if not self.alloc_rast_port_graphics(ctx, rp.addr, sdl_win, width, height):
                return 0, 0, 0
            rollback.callback(self.free_rast_port_graphics, ctx, rp.addr)
            self._rastport_resources[rp.addr] = rollback.pop_all()
        return rp.addr, layer.addr, bm.addr

    def free_RastPortStruct(self, ctx, rp_addr):
        owned = self._rastport_resources.pop(rp_addr, None)
        if owned is not None:
            owned.close()
            return
        rp = RastPortStruct(ctx.mem, rp_addr)
    
        # --- Free Layer ---
        layer_addr = rp.Layer.get()
        if layer_addr:
            layer = LayerStruct(ctx.mem, layer_addr)
    
            dl_addr = layer.DamageList.get()
            if dl_addr:
                ctx.cpu.w_reg(REG_A0, dl_addr)
                self.DisposeRegion(ctx)
            
            layer.free(ctx.alloc)
    
        # --- Free BitMap + planes ---
        bm_addr = rp.BitMap.get()
        if bm_addr:
            bm = BitMapStruct(ctx.mem, bm_addr)
            bytes_per_row = bm.BytesPerRow.get()
            rows = bm.Rows.get()
            depth = bm.Depth.get()
            plane_size = bytes_per_row * rows
    
            for i in range(depth):
                plane_addr = bm.Planes[i].get()
                if plane_addr:
                    ctx.alloc.free_mem(plane_addr, plane_size)
    
            bm.free(ctx.alloc)
    
        # --- Free RastPort ---
        rp.free(ctx.alloc)
    
        # --- Free SDL renderer + texture ---
        self.free_rast_port_graphics(ctx, rp_addr)

    def alloc_rast_port_graphics(self, ctx, rastport_addr, sdl_win, width, height):
        import sdl2

        renderer = sdl2.SDL_CreateRenderer(
            sdl_win,
            -1,
            sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC,
        )
        if not renderer:
            return False
        with ExitStack() as rollback:
            rollback.callback(sdl2.SDL_DestroyRenderer, renderer)
            texture = sdl2.SDL_CreateTexture(
                renderer, sdl2.SDL_PIXELFORMAT_RGBA8888,
                sdl2.SDL_TEXTUREACCESS_TARGET, width, height,
            )
            if not texture:
                return False
            rollback.callback(sdl2.SDL_DestroyTexture, texture)
            if sdl2.SDL_SetRenderTarget(renderer, texture) == -1:
                return False
            if sdl2.SDL_SetRenderDrawColor(renderer, 168, 168, 168, 255) == -1:
                return False
            if sdl2.SDL_RenderClear(renderer) == -1:
                return False
            if sdl2.SDL_SetRenderTarget(renderer, None) == -1:
                return False
            self.rp_graphics_map[rastport_addr] = RastPortGraphics(
                sdl_win, renderer, texture, width, height
            )
            rollback.pop_all()
        return True

    def free_rast_port_graphics(self, ctx, rastport_addr):
        import sdl2

        rp_graphics = self.rp_graphics_map.pop(rastport_addr, None)
        if rp_graphics:
            sdl2.SDL_DestroyTexture(rp_graphics.texture)
            sdl2.SDL_DestroyRenderer(rp_graphics.renderer)
        else:
            log_gfx.error(
                "free_rast_port_graphics: unknown rastport address 0x%08X",
                rastport_addr,
            )

    def get_rp_graphics(self, rastport_addr):
        rp_graphics = self.rp_graphics_map.get(rastport_addr, None)
        if not rp_graphics:
            log_gfx.error(
                "get_rp_graphics: unknown rastport address 0x%08X",
                rastport_addr,
            )
        return rp_graphics

    # ---------------------------------------------------------------------
    # Font handling
    # ---------------------------------------------------------------------

    def open_font_file(self, ctx, name: str, size: int):
        from sdl2 import sdlttf

        font_path = os.path.join(self.fontsPath, name)
        font = sdlttf.TTF_OpenFont(font_path.encode("utf-8"), size)
        if not font:
            log_main.error(
                "TTF_OpenFont failed for '%s': %s",
                name,
                sdlttf.TTF_GetError().decode("utf-8"),
            )
            return None, None

        with ExitStack() as rollback:
            rollback.callback(sdlttf.TTF_CloseFont, font)
            height = sdlttf.TTF_FontHeight(font)
            ascent = sdlttf.TTF_FontAscent(font)
            avg_width = ctypes.c_int()
            dummy = ctypes.c_int()
            if sdlttf.TTF_SizeUTF8(
                font, b"M", ctypes.byref(avg_width), ctypes.byref(dummy)
            ) != 0:
                return None, None
            font_mem = self.alloc.alloc_memory(
                TextFontStruct.get_size(), label="Graphics TextFont",
                except_on_failure=False,
            )
            if font_mem is None:
                return None, None
            rollback.callback(self.alloc.free_memory, font_mem)
            font_addr = font_mem.addr
            ctx.mem.clear_block(font_addr, font_mem.size, 0)
            tf = TextFontStruct(ctx.mem, font_addr)
            tf.tf_YSize.set(height)
            tf.tf_XSize.set(avg_width.value)
            tf.tf_Baseline.set(ascent)
            tf.tf_Accessors.set(1)
            tf.tf_LoChar.set(32)
            tf.tf_HiChar.set(127)
            self.font_registry[font_addr] = font
            rollback.pop_all()
        log_main.debug(
            "Loaded font '%s' size=%d height=%d ascent=%d avg_width=%d",
            name, size, height, ascent, avg_width.value,
        )
        return font, font_addr

    def OpenFont(self, ctx):
        font_addr = self._open_font(ctx, ctx.cpu.r_reg(REG_A0))
        ctx.cpu.w_reg(REG_D0, font_addr)

    def _open_font(self, ctx, text_attr_addr):
        from sdl2 import sdlttf

        text_attr = TextAttrStruct(ctx.mem, text_attr_addr)

        font_name = None
        name_ptr = text_attr.ta_Name.get()
        if name_ptr != 0:
            font_name = ctx.mem.r_cstr(name_ptr)

        if font_name is None or font_name == "topaz.font":
            font_name = "Topaz_a1200_v1.0.ttf"

        font_size = text_attr.ta_YSize.get()
        style_flags = text_attr.ta_Style.get()

        font, font_addr = self.open_font_file(ctx, font_name, font_size)
        if not font:
            return 0

        sdl_style = 0
        if style_flags & 0x01:
            sdl_style |= sdlttf.TTF_STYLE_UNDERLINE
        if style_flags & 0x02:
            sdl_style |= sdlttf.TTF_STYLE_BOLD
        if style_flags & 0x04:
            sdl_style |= sdlttf.TTF_STYLE_ITALIC

        with ExitStack() as rollback:
            rollback.callback(self._close_font, ctx, font_addr)
            sdlttf.TTF_SetFontStyle(font, sdl_style)
            rollback.pop_all()
        return font_addr

    def CloseFont(self, ctx):
        self._close_font(ctx, ctx.cpu.r_reg(REG_A1))

    def _close_font(self, ctx, font_addr):
        from sdl2 import sdlttf

        font = self.font_registry.pop(font_addr, None)

        if font:
            try:
                sdlttf.TTF_CloseFont(font)
            finally:
                self.alloc.free_memory(self.alloc.get_memory(font_addr))
        else:
            log_main.warn("CloseFont: unknown font address 0x%X", font_addr)

    def SetFont(self, ctx):
        self._set_font(ctx, ctx.cpu.r_reg(REG_A1), ctx.cpu.r_reg(REG_A0))

    def _set_font(self, ctx, rastport_addr, font_ptr):
        rp = RastPortStruct(ctx.mem, rastport_addr)
        rp.Font.set(font_ptr)

        if font_ptr == 0:
            return

        tf = TextFontStruct(ctx.mem, font_ptr)
        rp.TxFlags.set(tf.tf_Flags.get())
        rp.TxHeight.set(tf.tf_YSize.get())
        rp.TxWidth.set(tf.tf_XSize.get())
        rp.TxBaseline.set(tf.tf_Baseline.get())
        rp.AlgoStyle.set(0)

    # ---------------------------------------------------------------------
    # RastPort API
    # ---------------------------------------------------------------------

    def InitRastPort(self, ctx):
        rp_addr = ctx.cpu.r_reg(REG_A1)
        self.init_rastport_canonical(ctx, rp_addr)

    def _pen_color(self, ctx, rp, pen):
        # Pen fields are BYTEs, but their bits select an unsigned palette
        # index. Only the attached bitmap's planes participate in a color.
        index = pen & 0xFF
        if rp.BitMap.val:
            depth = BitMapStruct(ctx.mem, rp.BitMap.val).Depth.val
            if 1 <= depth <= 8:
                index &= (1 << depth) - 1
        return self.palette.get(index)

    def _text_layout(self, ctx, rp, string_ptr, count):
        """Read a counted Amiga byte string and measure the queued text."""
        from sdl2 import sdlttf

        font = self.font_registry.get(rp.Font.val or self.topaz_font)
        if not font:
            log_gfx.error("Text: no usable font available")
            return None
        # Amiga strings are bytes, not UTF-8. A counted NUL is a glyph,
        # rather than SDL_ttf's string terminator; use its missing glyph.
        string = bytes(ctx.mem.r_block(string_ptr, count)).decode("latin-1")
        string = string.replace("\0", "\ufffd")
        spacing = rp.TxSpacing.val
        parts = list(string) if spacing else [string]
        runs = []
        advance = 0
        for part in parts:
            width, height = ctypes.c_int(), ctypes.c_int()
            if sdlttf.TTF_SizeUTF8(
                font, part.encode("utf-8"), ctypes.byref(width), ctypes.byref(height)
            ) != 0:
                log_gfx.error("Text: TTF_SizeUTF8 failed")
                return None
            runs.append((advance, part))
            advance += width.value + (spacing if spacing else 0)
        return font, runs, advance

    def TextLength(self, ctx):
        count = ctx.cpu.r_reg(REG_D0) & 0xFFFF
        if not count:
            ctx.cpu.w_reg(REG_D0, 0)
            return
        rp = RastPortStruct(ctx.mem, ctx.cpu.r_reg(REG_A1))
        layout = self._text_layout(ctx, rp, ctx.cpu.r_reg(REG_A0), count)
        ctx.cpu.w_reg(REG_D0, (layout[2] & 0xFFFF) if layout else 0)

    def Text(self, ctx):
        count = ctx.cpu.r_reg(REG_D0) & 0xFFFF
        if not count:
            return
        rastport_addr = ctx.cpu.r_reg(REG_A1)
        rp = RastPortStruct(ctx.mem, rastport_addr)
        layout = self._text_layout(ctx, rp, ctx.cpu.r_reg(REG_A0), count)
        if layout is None:
            return
        font, runs, advance = layout
        rp_graphics = self.get_rp_graphics(rastport_addr)
        if rp_graphics is not None:
            fg = self._pen_color(ctx, rp, rp.FgPen.val)
            bg = self._pen_color(ctx, rp, rp.BgPen.val)
            for offset, string in runs:
                rp_graphics.batch.texts.append(
                    BFText(rp.cp_x.val + offset, rp.cp_y.val - rp.TxBaseline.val,
                           string, font, fg, bg, rp.DrawMode.val)
                )
        # The public position is a signed WORD and keeps the same baseline.
        rp.cp_x.val = ((rp.cp_x.val + advance + 0x8000) & 0xFFFF) - 0x8000

    def Move(self, ctx):
        rastport_addr = ctx.cpu.r_reg(REG_A1)
        x = ctx.cpu.r_reg(REG_D0) & 0xFFFF
        y = ctx.cpu.r_reg(REG_D1) & 0xFFFF

        if x & 0x8000:
            x -= 0x10000
        if y & 0x8000:
            y -= 0x10000

        rp = RastPortStruct(ctx.mem, rastport_addr)
        rp.cp_x.set(x)
        rp.cp_y.set(y)

    def Draw(self, ctx):
        rastport_addr = ctx.cpu.r_reg(REG_A1)
        rp = RastPortStruct(ctx.mem, rastport_addr)
        rp_graphics = self.get_rp_graphics(rastport_addr)
    
        x = ctx.cpu.r_reg(REG_D0) & 0xffff
        y = ctx.cpu.r_reg(REG_D1) & 0xffff

        if x & 0x8000:
            x -= 0x10000
        if y & 0x8000:
            y -= 0x10000
    
        start_x = rp.cp_x.get()
        start_y = rp.cp_y.get()
    
        color = self._pen_color(ctx, rp, rp.FgPen.get())
        draw_mode = rp.DrawMode.get()
    
        rp_graphics.batch.draws.append(
            BFDraw(start_x, start_y, x, y, color, draw_mode)
        )
    
        rp.cp_x.set(x)
        rp.cp_y.set(y)

    def RectFill(self, ctx):
        rastport_addr = ctx.cpu.r_reg(REG_A1)
        rp = RastPortStruct(ctx.mem, rastport_addr)
        rp_graphics = self.get_rp_graphics(rastport_addr)
    
        x1 = ctx.cpu.r_reg(REG_D0) & 0xffff
        y1 = ctx.cpu.r_reg(REG_D1) & 0xffff
        x2 = ctx.cpu.r_reg(REG_D2) & 0xffff
        y2 = ctx.cpu.r_reg(REG_D3) & 0xffff
    
        if x1 & 0x8000:
            x1 -= 0x10000
        if y1 & 0x8000:
            y1 -= 0x10000
        if x2 & 0x8000:
            x2 -= 0x10000
        if y2 & 0x8000:
            y2 -= 0x10000
    
        left = min(x1, x2)
        top = min(y1, y2)
        w = abs(x2 - x1) + 1
        h = abs(y2 - y1) + 1
    
        color = self._pen_color(ctx, rp, rp.FgPen.get())
        draw_mode = rp.DrawMode.get()
    
        rp_graphics.batch.rectfills.append(
            BFRectFill(left, top, w, h, color, draw_mode)
        )


    def SetAPen(self, ctx):
        rastport_addr = ctx.cpu.r_reg(REG_A1)
        pen = ctx.cpu.r_reg(REG_D0) & 0xFF
        if pen >= 0x80:
            pen -= 0x100

        rp = RastPortStruct(ctx.mem, rastport_addr)
        rp.FgPen.set(pen)

    def SetDrMd(self, ctx):
        rastport_addr = ctx.cpu.r_reg(REG_A1)
        mode = ctx.cpu.r_reg(REG_D0) & 0xFF

        rp = RastPortStruct(ctx.mem, rastport_addr)
        rp.DrawMode.set(mode)

    # ---------------------------------------------------------------------
    # Helper: invalidate → SDL_USEREVENT_REPAINT
    # ---------------------------------------------------------------------

    def invalidate(self, ctx, rastport_addr):
        ctx.exec_lib.intuition_lib.refresh(ctx, rastport_addr)

    def NewRegion(self, ctx):
        reg_addr = self._new_region(ctx)
        ctx.cpu.w_reg(REG_D0, reg_addr)

    def DisposeRegion(self, ctx):
        region_addr = ctx.cpu.r_reg(REG_A0)
        self._dispose_region(ctx, region_addr)

    def ClearRegion(self, ctx):
        region_addr = ctx.cpu.r_reg(REG_A0)
        self._clear_region(ctx, region_addr)

    def OrRectRegion(self, ctx):
        region_addr = ctx.cpu.r_reg(REG_A0)
        rect_addr   = ctx.cpu.r_reg(REG_A1)
    
        if region_addr == 0 or rect_addr == 0:
            ctx.cpu.w_reg(REG_D0, 0)
            return
    
        ctx.cpu.w_reg(REG_D0, self._or_rect_region(ctx, region_addr, rect_addr))

    def OrRegionRegion(self, ctx):
        cpu = ctx.cpu
        src_region_addr = cpu.r_reg(REG_A0)
        dest_region_addr = cpu.r_reg(REG_A1)

        rc = self._or_region_region(ctx, src_region_addr, dest_region_addr)
        cpu.w_reg(REG_D0, rc)
        
    def AndRegionRegion(self, ctx):
        cpu = ctx.cpu
        src_region_addr  = cpu.r_reg(REG_A0)
        dest_region_addr = cpu.r_reg(REG_A1)
    
        rc = self._and_region_region(ctx, src_region_addr, dest_region_addr)
        cpu.w_reg(REG_D0, rc)


    def _new_region(self, ctx):
        """Allocate an empty Region."""
        memory = ctx.alloc.alloc_memory(
            RegionStruct.get_size(), label="Graphics region", except_on_failure=False
        )
        if memory is None:
            return 0
        ctx.mem.clear_block(memory.addr, memory.size, 0)
        reg = RegionStruct(ctx.mem, memory.addr)
        reg.bounds.MaxX.val = reg.bounds.MaxY.val = -1
        return reg.addr

    def _dispose_region(self, ctx, region_addr):
        """
        Free a Region and all its RegionRectangles.
        Equivalent to graphics.library DisposeRegion().
        """
        if region_addr == 0:
            return
    
        # Clear all rectangles (frees RegionRectangle nodes)
        self._clear_region(ctx, region_addr)
    
        # Free the RegionStruct itself
        RegionStruct(ctx.mem, region_addr).free(ctx.alloc)


    def _clear_region(self, ctx, region_addr):
        """Remove all rectangles from a Region."""
        reg = RegionStruct(ctx.mem, region_addr)
    
        rr_addr = reg.RegionRectangle.get()
        while rr_addr != 0:
            rr = RegionRectangleStruct(ctx.mem, rr_addr)
            next_rr = rr.Next.get()
    
            # Free this node
            rr.free(ctx.alloc)
    
            rr_addr = next_rr
    
        # Reset region to empty
        reg.RegionRectangle.set(0)
        reg.bounds.MinX.set(0)
        reg.bounds.MinY.set(0)
        reg.bounds.MaxX.set(-1)
        reg.bounds.MaxY.set(-1)

    @staticmethod
    def _bounds(rect):
        return rect.MinX.val, rect.MinY.val, rect.MaxX.val, rect.MaxY.val

    @staticmethod
    def _write_bounds(rect, bounds):
        for name, value in zip(("MinX", "MinY", "MaxX", "MaxY"), bounds):
            rect.get(name).val = value

    def _region_rects(self, ctx, region_addr):
        region = RegionStruct(ctx.mem, region_addr)
        x, y = region.bounds.MinX.val, region.bounds.MinY.val
        result = []
        addr = region.RegionRectangle.val
        while addr:
            node = RegionRectangleStruct(ctx.mem, addr)
            left, top, right, bottom = self._bounds(node.bounds)
            result.append((x + left, y + top, x + right, y + bottom))
            addr = node.Next.val
        return result

    @staticmethod
    def _region_union(rects):
        """Create disjoint, sorted horizontal bands without pixel expansion."""
        rects = [r for r in rects if r[0] <= r[2] and r[1] <= r[3]]
        levels = sorted({v for r in rects for v in (r[1], r[3] + 1)})
        result = []
        previous = None
        for top, end in zip(levels, levels[1:]):
            intervals = sorted((a, c) for a, b, c, d in rects if b <= top <= d)
            merged = []
            for left, right in intervals:
                if merged and left <= merged[-1][1] + 1:
                    merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
                else:
                    merged.append((left, right))
            if merged and previous == merged:
                for index in range(len(result) - len(merged), len(result)):
                    a, b, c, _ = result[index]
                    result[index] = (a, b, c, end - 1)
            else:
                result.extend((a, top, c, end - 1) for a, c in merged)
            previous = merged
        return result

    def _replace_region(self, ctx, region_addr, rects):
        rects = self._region_union(rects)
        if not rects:
            self._clear_region(ctx, region_addr)
            return 1
        bounds = (min(r[0] for r in rects), min(r[1] for r in rects),
                  max(r[2] for r in rects), max(r[3] for r in rects))
        with ExitStack() as rollback:
            nodes = []
            for left, top, right, bottom in rects:
                memory = ctx.alloc.alloc_memory(
                    RegionRectangleStruct.get_size(), label="Region rectangle",
                    except_on_failure=False,
                )
                if memory is None:
                    return 0
                rollback.callback(ctx.alloc.free_memory, memory)
                ctx.mem.clear_block(memory.addr, memory.size, 0)
                node = RegionRectangleStruct(ctx.mem, memory.addr)
                self._write_bounds(node.bounds, (
                    left - bounds[0], top - bounds[1],
                    right - bounds[0], bottom - bounds[1],
                ))
                if nodes:
                    nodes[-1].Next.val = node.addr
                    node.Prev.val = nodes[-1].addr
                nodes.append(node)
            # Keep the old region untouched until every replacement exists.
            self._clear_region(ctx, region_addr)
            region = RegionStruct(ctx.mem, region_addr)
            self._write_bounds(region.bounds, bounds)
            region.RegionRectangle.val = nodes[0].addr
            rollback.pop_all()
        return 1

    def _or_rect_region(self, ctx, region_addr, rect_addr):
        rect = self._bounds(RectangleStruct(ctx.mem, rect_addr))
        return self._replace_region(ctx, region_addr,
                                    self._region_rects(ctx, region_addr) + [rect])

    def _or_region_region(self, ctx, src_region_addr, dest_region_addr):
        if not src_region_addr or not dest_region_addr:
            return 0
        if src_region_addr == dest_region_addr:
            return 1
        return self._replace_region(
            ctx, dest_region_addr, self._region_rects(ctx, dest_region_addr)
            + self._region_rects(ctx, src_region_addr),
        )

    def _and_region_region(self, ctx, src_region_addr, dest_region_addr):
        if not src_region_addr or not dest_region_addr:
            return 0
        if src_region_addr == dest_region_addr:
            return 1
        intersections = []
        for a, b, c, d in self._region_rects(ctx, src_region_addr):
            for e, f, g, h in self._region_rects(ctx, dest_region_addr):
                intersections.append((max(a, e), max(b, f), min(c, g), min(d, h)))
        return self._replace_region(ctx, dest_region_addr, intersections)

    def _get_damage_clip_rect_for_rp(self, ctx, rastport_addr):
        """
        Resolve the DamageList Region for this RastPort and
        return an SDL_Rect (or None if no clipping).
        """
        import sdl2
        # 1) Map RastPort -> Window
        # You already have rp_2_win_addr for refresh, so reuse it.
        try:
            win_addr = ctx.exec_lib.intuition_lib.rp_2_win_addr[rastport_addr]
        except KeyError:
            return None
    
        window = WindowStruct(ctx.mem, win_addr)
        layer_addr = window.WLayer.get()
        if layer_addr == 0:
            return None
    
        layer = LayerStruct(ctx.mem, layer_addr)
        region_addr = layer.DamageList.get()
        if region_addr == 0:
            return None
    
        reg = RegionStruct(ctx.mem, region_addr)
    
        # Empty region?
        maxx = reg.bounds.MaxX.get()
        minx = reg.bounds.MinX.get()
        if maxx < minx:
            # Region empty → no clipping
            return None
    
        minx = reg.bounds.MinX.get()
        miny = reg.bounds.MinY.get()
        maxx = reg.bounds.MaxX.get()
        maxy = reg.bounds.MaxY.get()
    
        w = (maxx - minx) + 1
        h = (maxy - miny) + 1
    
        # Clamp to non-negative; SDL doesn't like negative sizes
        if w <= 0 or h <= 0:
            return None
    
        return sdl2.SDL_Rect(minx, miny, w, h)
    
class RastPortGraphics:
    def __init__(self, sdl_win, renderer, texture, width, height):
        import sdl2
        self.sdl_window_id = sdl2.SDL_GetWindowID(sdl_win)
        self.renderer = renderer
        self.texture = texture
        self.width = width
        self.height = height
        self.batch = RPBatch()


def create_amiga_palette():
    import sdl2

    palette = {}

    wb2_colors = [
        (168, 168, 168),      # 4: Amiga Gray (our default bg)
        (0x00, 0x00, 0x00),   # 0: Black
        (0xFF, 0xFF, 0xFF),   # 1: White
        (0x88, 0xAA, 0xFF),   # 2: Light Blue
        (0x00, 0x66, 0xAA),   # 3: Dark Blue
        (0x66, 0x66, 0x66),   # 5: Dark Gray
        (0xFF, 0xAA, 0x00),   # 6: Orange
        (0xAA, 0x00, 0x00),   # 7: Red
    ]

    for i in range(8):
        r, g, b = wb2_colors[i]
        palette[i] = sdl2.SDL_Color(r, g, b, 255)

    for i in range(8, 32):
        r = ((i >> 0) & 0x03) * 85
        g = ((i >> 2) & 0x03) * 85
        b = ((i >> 4) & 0x03) * 85
        palette[i] = sdl2.SDL_Color(r, g, b, 255)

    # Eight-plane bitmaps may address every byte-valued pen.
    for i in range(32, 256):
        palette[i] = sdl2.SDL_Color(
            ((i >> 5) & 7) * 255 // 7,
            ((i >> 2) & 7) * 255 // 7,
            (i & 3) * 85, 255,
        )

    return palette


class RPBatch:
    def __init__(self):
        self.rectfills = []
        self.draws = []
        self.texts = []

    def clear(self):
        self.rectfills.clear()
        self.draws.clear()
        self.texts.clear()

@dataclass
class BFRectFill:
    x: int
    y: int
    w: int
    h: int
    color: "sdl2.SDL_Color"
    draw_mode: int

@dataclass
class BFDraw:
    x1: int
    y1: int
    x2: int
    y2: int
    color: "sdl2.SDL_Color"
    draw_mode: int

@dataclass
class BFText:
    x: int
    y: int
    string: str
    font: object
    fg: "sdl2.SDL_Color"
    bg: "sdl2.SDL_Color"
    draw_mode: int
