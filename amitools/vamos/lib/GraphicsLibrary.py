import os
import time
import struct
from contextlib import ExitStack

from amitools.vamos.libcore.impl import LibImpl
from amitools.vamos.machine.regs import (
    REG_A0,
    REG_D0,
    REG_A1,
    REG_D1,
    REG_D2,
    REG_D3,
    REG_D4,
    REG_D5,
)
from amitools.vamos.lib.graphics import (
    TextAttrStruct,
    BitMapStruct,
    RastPortStruct,
    RegionRectangleStruct,
    RegionStruct,
    RectangleStruct,
    LayerStruct,
    JAM2,
)
from amitools.vamos.lib.intuition import TextFontStruct, WindowStruct
from amitools.vamos.log import log_main, log_gfx
from dataclasses import dataclass
from amitools.vamos.display import get_display
from amitools.vamos.display.base import Rect, Color
from amitools.vamos.lib.graphics_surface import RasterState, RasterSurface
from amitools.vamos.lib.graphics_support import GraphicsSupport
from amitools.vamos.lib.graphics_base import GfxBaseStruct
from amitools.vamos.libtypes import List
from amitools.vamos.libstructs import NodeType
from amitools.vamos.lib.graphics_font import (
    BitmapFont,
    load_topaz_font,
)


class GraphicsLibrary(GraphicsSupport, LibImpl):
    def get_struct_def(self):
        return GfxBaseStruct

    def __init__(self):
        super().__init__()
        self.alloc = None
        self.fontsPath = None
        self.text_attr = None
        self.font_registry = {}
        self._font_owners = {}
        self.topaz_font = None
        self.rp_graphics_map = {}
        self._rastport_resources = {}
        self._window_planes = {}
        self.palette = None
        self.screen_palettes = {}
        self._color_maps = {}
        self._color_palettes = {}
        self._pen_refs = {}
        self._bitmaps = {}
        self._lib_opened = False
        self._setup_resources = None

    # ---------------------------------------------------------------------
    # Library setup / teardown
    # ---------------------------------------------------------------------

    def EraseRect(self, ctx, rp, xMin, yMin, xMax, yMax):
        port = RastPortStruct(ctx.mem, rp)
        state = self._raster_state(ctx, port)
        if state is None:
            return
        state.foreground, state.mode = port.BgPen.val & 255, 0
        state.area_pattern = ()
        xMin, yMin, xMax, yMax = [
            ((v + 32768) & 65535) - 32768
            for v in (xMin, yMin, xMax, yMax)
        ]
        backing = self.get_rp_graphics(rp)
        if backing:
            backing.batch.add(
                BFRectFill(xMin, yMin, xMax - xMin + 1, yMax - yMin + 1,
                           None, 0, state)
            )

    def setup_lib(self, ctx, base_addr):
        self.alloc = ctx.alloc
        ctx.exec_lib.graphics_lib = self
        self.display = get_display(ctx)
        self.gfx_base = GfxBaseStruct(ctx.mem, base_addr)
        List(ctx.mem, self.gfx_base.TextFonts.addr).new(NodeType.NT_FONT)
        self.gfx_base.DisplayFlags.val = 4  # PAL
        self.gfx_base.NormalDisplayRows.val = 256
        self.gfx_base.NormalDisplayColumns.val = 320
        self.gfx_base.MicrosPerLine.val = 64 << 8

    def open_lib(self, ctx, open_cnt):
        if self._lib_opened:
            return
        self.display = get_display(ctx)
        self.display.open_fonts()
        try:
            with ExitStack() as rollback:
                rollback.callback(self.display.close_fonts)
                self.fontsPath = ctx.path_mgr.to_sys_path("FONTS:")
                if self.fontsPath is None:
                    self.fontsPath = os.path.join(os.path.dirname(__file__), "fonts")
                attr_memory = ctx.alloc.alloc_memory(
                    TextAttrStruct.get_size(),
                    label="Graphics default TextAttr",
                    except_on_failure=False,
                )
                if attr_memory is None:
                    return
                rollback.callback(ctx.alloc.free_memory, attr_memory)
                ctx.mem.clear_block(attr_memory.addr, attr_memory.size, 0)
                attr = TextAttrStruct(ctx.mem, attr_memory.addr)
                name = "topaz.font"
                name_memory = ctx.alloc.alloc_memory(
                    len(name) + 1,
                    label="Graphics default name",
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
                if hasattr(self, "gfx_base"):
                    self.gfx_base.DefaultFont.val = font_addr
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
        if hasattr(self, "gfx_base"):
            self.gfx_base.DefaultFont.val = 0
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

    def create_window_rastport(self, ctx, window, width, height, depth=2):
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
            planes = ExitStack()
            for i in range(depth):
                planes.callback(ctx.alloc.free_mem, bm.Planes[i].val, plane_size)
            self._window_planes[bm.addr] = planes
            rollback.callback(self._free_window_planes, bm.addr)
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
            if not self.alloc_rast_port_graphics(ctx, rp.addr, window, width, height):
                return 0, 0, 0
            rollback.callback(self.free_rast_port_graphics, ctx, rp.addr)
            self._rastport_resources[rp.addr] = rollback.pop_all()
        return rp.addr, layer.addr, bm.addr

    def _free_window_planes(self, bitmap):
        owner = self._window_planes.pop(bitmap, None)
        if owner is not None:
            owner.close()

    def resize_window_rastport(self, ctx, rp_addr, width, height):
        """Replace pixels and texture atomically, keeping guest pointers stable."""

        backing = self.rp_graphics_map.get(rp_addr)
        if backing is None or not (0 < width <= 32767 and 0 < height <= 32767):
            return False
        if (backing.width, backing.height) == (width, height):
            return True
        ctx.exec_lib.intuition_lib._flush_batch(backing)
        rp = RastPortStruct(ctx.mem, rp_addr)
        old = BitMapStruct(ctx.mem, rp.BitMap.val)
        with ExitStack() as rollback:
            addr = self.AllocBitMap(ctx, width, height, old.Depth.val, 1, 0)
            if not addr:
                return False
            rollback.callback(self.FreeBitMap, ctx, addr)
            new = BitMapStruct(ctx.mem, addr)
            frame = backing.frame.replacement(width, height)
            if frame is None:
                return False
            rollback.callback(frame.close)
            stride = min(old.BytesPerRow.val, new.BytesPerRow.val)
            for plane in range(old.Depth.val):
                for y in range(min(old.Rows.val, height)):
                    ctx.mem.w_block(new.Planes[plane].val + y * new.BytesPerRow.val,
                                    ctx.mem.r_block(old.Planes[plane].val + y * old.BytesPerRow.val, stride))
            surface = RasterSurface(width, height)
            # The scratch descriptor remains owned with its planes. The
            # original public descriptor and RastPort never move.
            ctx.mem.w_block(old.addr, ctx.mem.r_block(addr, BitMapStruct.get_size()))
            self._free_window_planes(old.addr)
            self._window_planes[old.addr] = self._bitmaps.pop(addr)
            backing.frame.close()
            backing.frame, backing.surface = frame, surface
            backing.width, backing.height = width, height
            surface.load(self._raster_state(ctx, rp))
            surface.dirty = True
            if rp.Layer.val:
                layer = LayerStruct(ctx.mem, rp.Layer.val)
                layer.Width.val, layer.Height.val = width, height
                layer.bounds.MaxX.val = layer.bounds.MinX.val + width - 1
                layer.bounds.MaxY.val = layer.bounds.MinY.val + height - 1
                self._replace_region(ctx, layer.DamageList.val, [(0, 0, width - 1, height - 1)])
            rollback.pop_all()
        return True

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

        # Release the host framebuffer.
        self.free_rast_port_graphics(ctx, rp_addr)

    def alloc_rast_port_graphics(self, ctx, rastport_addr, window, width, height):
        self.display = get_display(ctx)
        frame = self.display.create_frame(window, width, height)
        if frame is None:
            return False
        self.rp_graphics_map[rastport_addr] = RastPortGraphics(window, frame, width, height)
        return True


    def free_rast_port_graphics(self, ctx, rastport_addr):
        graphics = self.rp_graphics_map.pop(rastport_addr, None)
        if graphics is not None:
            with ExitStack() as cleanup:
                cleanup.callback(graphics.frame.close)
                cleanup.callback(graphics.batch.clear)


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

    def open_font_file(self, ctx, name, size, style=0, amiga_name=None):
        path = os.path.join(self.fontsPath, name)
        if name == "Cousine-Regular.ttf" and not os.path.isfile(path):
            path = os.path.join(os.path.dirname(__file__), "fonts", name)
        font = get_display(ctx).open_font(path, size, style)
        if font is None:
            return None, None
        addr = self._store_font(ctx, font, amiga_name or name, font.height,
                                font.baseline, font.width, font.strike)
        return (font, addr) if addr else (None, None)


    def _store_font(self, ctx, font, name, height, ascent, width, strike):
        with ExitStack() as rollback:
            name_bytes = name.encode("latin-1") + b"\0"
            if len(name_bytes) & 1:
                name_bytes += b"\0"
            count = len(strike.locations)
            locations = struct.pack(">" + "I" * count, *strike.locations)
            spaces = struct.pack(">" + "h" * count, *strike.spaces)
            kerns = struct.pack(">" + "h" * count, *strike.kerns)
            payload = name_bytes + locations + spaces + kerns + strike.data
            font_mem = self.alloc.alloc_memory(
                TextFontStruct.get_size() + len(payload),
                label="Graphics TextFont",
                except_on_failure=False,
            )
            if font_mem is None:
                return 0
            rollback.callback(self.alloc.free_memory, font_mem)
            font_addr = font_mem.addr
            ctx.mem.clear_block(font_addr, font_mem.size, 0)
            tf = TextFontStruct(ctx.mem, font_addr)
            tf.tf_YSize.set(height)
            tf.tf_XSize.set(width)
            tf.tf_Baseline.set(ascent)
            tf.tf_Accessors.set(1)
            tf.tf_LoChar.set(32)
            tf.tf_HiChar.set(255)
            tf.tf_Flags.val = 0x20  # FPF_PROPORTIONAL: use spacing/kerning tables
            tf.tf_BoldSmear.val = 1
            # Keep all public tables in the font allocation. CloseFont and
            # rollback release them even if the caller edits public pointers.
            data_addr = font_addr + TextFontStruct.get_size()
            ctx.mem.w_block(data_addr, payload)
            tf.tf_Message.mn_Node.ln_Name.aptr = data_addr
            tf.tf_CharLoc.val = data_addr + len(name_bytes)
            tf.tf_CharSpace.val = tf.tf_CharLoc.val + len(locations)
            tf.tf_CharKern.val = tf.tf_CharSpace.val + len(spaces)
            tf.tf_CharData.val = tf.tf_CharKern.val + len(kerns)
            tf.tf_Modulo.val = strike.modulo
            self.font_registry[font_addr] = font
            self._font_owners[font_addr] = {"font": font, "refs": 1}
            rollback.pop_all()
        return font_addr

    def OpenFont(self, ctx):
        font_addr = self._open_font(ctx, ctx.cpu.r_reg(REG_A0))
        ctx.cpu.w_reg(REG_D0, font_addr)

    def _open_font(self, ctx, text_attr_addr):

        text_attr = TextAttrStruct(ctx.mem, text_attr_addr)

        font_name = None
        name_ptr = text_attr.ta_Name.get()
        if name_ptr != 0:
            font_name = ctx.mem.r_cstr(name_ptr)

        amiga_name = font_name or "topaz.font"
        if font_name is None or font_name.lower() == "topaz.font":
            font_name = "Cousine-Regular.ttf"

        font_size = text_attr.ta_YSize.get()
        style_flags = text_attr.ta_Style.get()
        if amiga_name.lower() == "topaz.font" and font_size == 8 and not style_flags:
            bitmap = load_topaz_font()
            if bitmap is not None:
                addr = self._store_font(
                    ctx,
                    bitmap,
                    amiga_name,
                    bitmap.height,
                    bitmap.baseline,
                    bitmap.width,
                    bitmap.strike,
                )
                if addr:
                    TextFontStruct(
                        ctx.mem, addr
                    ).tf_Flags.val = 0x41  # designed ROM font
                return addr

        font, font_addr = self.open_font_file(
            ctx, font_name, font_size, style_flags, amiga_name
        )
        if not font:
            return 0
        TextFontStruct(ctx.mem, font_addr).tf_Style.val = style_flags
        return font_addr

    def CloseFont(self, ctx):
        self._close_font(ctx, ctx.cpu.r_reg(REG_A1))

    @staticmethod
    def _release_host_font(owner):
        owner["refs"] -= 1


    def _retain_host_font(self, font_addr):
        owner = self._font_owners.get(font_addr)
        if owner is None:
            return None
        owner["refs"] += 1
        return lambda: self._release_host_font(owner)

    def _close_font(self, ctx, font_addr):
        font = self.font_registry.pop(font_addr, None)
        if font is None:
            return
        owner = self._font_owners.pop(font_addr)
        try:
            self._release_host_font(owner)
        finally:
            self.alloc.free_memory(self.alloc.get_memory(font_addr))

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
        backing = self.rp_graphics_map.get(rp.addr)
        palette = getattr(backing, "palette", None) or self.palette
        return palette.get(index)

    def _text_layout(self, ctx, rp, string_ptr, count):
        font = self.font_registry.get(rp.Font.val or self.topaz_font)
        if font is None:
            return None
        string = bytes(ctx.mem.r_block(string_ptr, count)).decode("latin-1").replace("\0", "\ufffd")
        spacing = rp.TxSpacing.val
        parts = list(string) if spacing else [string]
        runs, advance = [], 0
        for part in parts:
            metrics = get_display(ctx).text_size(font, part)
            if metrics is None:
                return None
            width, height = metrics
            runs.append((advance, part))
            advance += width + (spacing if spacing else 0)
        return font, runs, advance


    def _raster_state(self, ctx, rp):
        if not rp.BitMap.val:
            return None
        bitmap = BitMapStruct(ctx.mem, rp.BitMap.val)
        depth = min(bitmap.Depth.val, 8)
        return RasterState(
            ctx.mem,
            tuple(bitmap.Planes[i].val for i in range(depth)),
            bitmap.BytesPerRow.val,
            rp.Mask.val & ((1 << depth) - 1),
            rp.FgPen.val & 255,
            rp.BgPen.val & 255,
            rp.DrawMode.val,
            rp.LinePtrn.val,
            rp.TxSpacing.val,
            tuple(
                ctx.mem.r16(rp.AreaPtrn.val + n * 2)
                for n in range(1 << rp.AreaPtSz.val)
            ) if rp.AreaPtrn.val and 0 <= rp.AreaPtSz.val <= 8 else (),
        )

    def TextLength(self, ctx):
        count = ctx.cpu.r_reg(REG_D0) & 0xFFFF
        if not count:
            ctx.cpu.w_reg(REG_D0, 0)
            return
        rp = RastPortStruct(ctx.mem, ctx.cpu.r_reg(REG_A1))
        guest = self._guest_text(ctx, rp, ctx.cpu.r_reg(REG_A0), count, False)
        if guest is not None:
            ctx.cpu.w_reg(REG_D0, guest & 0xFFFF)
            return
        layout = self._text_layout(ctx, rp, ctx.cpu.r_reg(REG_A0), count)
        ctx.cpu.w_reg(REG_D0, (layout[2] & 0xFFFF) if layout else 0)

    def Text(self, ctx):
        count = ctx.cpu.r_reg(REG_D0) & 0xFFFF
        if not count:
            return
        rastport_addr = ctx.cpu.r_reg(REG_A1)
        rp = RastPortStruct(ctx.mem, rastport_addr)
        guest = self._guest_text(ctx, rp, ctx.cpu.r_reg(REG_A0), count, True)
        if guest is not None:
            rp.cp_x.val = ((rp.cp_x.val + guest + 0x8000) & 0xFFFF) - 0x8000
            return
        layout = self._text_layout(ctx, rp, ctx.cpu.r_reg(REG_A0), count)
        if layout is None:
            return
        font, runs, advance = layout
        rp_graphics = self.get_rp_graphics(rastport_addr)
        if rp_graphics is not None:
            fg = self._pen_color(ctx, rp, rp.FgPen.val)
            bg = self._pen_color(ctx, rp, rp.BgPen.val)
            for offset, string in runs:
                rp_graphics.batch.add(
                    BFText(
                        rp.cp_x.val + offset,
                        rp.cp_y.val - rp.TxBaseline.val,
                        string,
                        font,
                        fg,
                        bg,
                        rp.DrawMode.val,
                        self._retain_host_font(rp.Font.val or self.topaz_font),
                        self._raster_state(ctx, rp),
                    )
                )
        # The public position is a signed WORD and keeps the same baseline.
        rp.cp_x.val = ((rp.cp_x.val + advance + 0x8000) & 0xFFFF) - 0x8000

    @staticmethod
    def _word(value):
        return ((value + 0x8000) & 0xFFFF) - 0x8000

    @staticmethod
    def _template_bits(mem, address, bit_offset, stride, width, height):
        # Copy at call time: clients reuse and free templates before repaint.
        result = bytearray(width * height)
        first_byte, first_bit = divmod(bit_offset, 8)
        byte_count = (first_bit + width + 7) // 8
        for y in range(height):
            row = mem.r_block(address + y * stride + first_byte, byte_count)
            for x in range(width):
                bit = first_bit + x
                result[y * width + x] = bool(row[bit // 8] & (0x80 >> (bit & 7)))
        return bytes(result)

    def _queue_template(self, ctx, rp, x, y, width, height, pixels):
        if not width or not height:
            return
        state = self._raster_state(ctx, rp)
        if state is None:
            return
        command = BFTemplate(x, y, width, height, pixels, state)
        backing = self.rp_graphics_map.get(rp.addr)
        if backing is not None:
            backing.batch.add(command)
        else:
            # Offscreen RastPorts are guest-owned and need no host framebuffer.
            bitmap = BitMapStruct(ctx.mem, rp.BitMap.val)
            surface = RasterSurface(bitmap.BytesPerRow.val * 8, bitmap.Rows.val)
            surface.load(state)
            surface.template(state, x, y, width, height, pixels)

    def _guest_text(self, ctx, rp, string_ptr, count, draw):
        if not rp.Font.val:
            return None
        font = TextFontStruct(ctx.mem, rp.Font.val)
        if not font.tf_CharLoc.val or not font.tf_CharData.val:
            return None
        if font.tf_HiChar.val < font.tf_LoChar.val:
            return 0
        position = 0
        proportional = font.tf_Flags.val & 0x20
        for char in ctx.mem.r_block(string_ptr, count):
            index = char - font.tf_LoChar.val
            if not 0 <= index <= font.tf_HiChar.val - font.tf_LoChar.val:
                index = font.tf_HiChar.val - font.tf_LoChar.val + 1
            kern = (
                self._word(ctx.mem.r16(font.tf_CharKern.val + index * 2))
                if proportional and font.tf_CharKern.val
                else 0
            )
            space = (
                self._word(ctx.mem.r16(font.tf_CharSpace.val + index * 2))
                if proportional and font.tf_CharSpace.val
                else font.tf_XSize.val
            )
            advance = kern + space + rp.TxSpacing.val
            if draw:
                location = ctx.mem.r32(font.tf_CharLoc.val + index * 4)
                ink_width, height = location & 0xFFFF, font.tf_YSize.val
                left = min(0, kern)
                width = max(0, advance, kern + ink_width) - left
                ink = self._template_bits(
                    ctx.mem,
                    font.tf_CharData.val,
                    location >> 16,
                    font.tf_Modulo.val,
                    ink_width,
                    height,
                )
                pixels = bytearray(width * height)
                for row in range(height):
                    start = row * width + kern - left
                    pixels[start : start + ink_width] = ink[
                        row * ink_width : (row + 1) * ink_width
                    ]
                self._queue_template(
                    ctx,
                    rp,
                    rp.cp_x.val + position + left,
                    rp.cp_y.val - font.tf_Baseline.val,
                    width,
                    height,
                    bytes(pixels),
                )
            position += advance
        return position

    def BltTemplate(self, ctx):
        rp = RastPortStruct(ctx.mem, ctx.cpu.r_reg(REG_A1))
        width, height = ctx.cpu.r_reg(REG_D4) & 0xFFFF, ctx.cpu.r_reg(REG_D5) & 0xFFFF
        if not width or not height:
            return
        pixels = self._template_bits(
            ctx.mem,
            ctx.cpu.r_reg(REG_A0),
            ctx.cpu.r_reg(REG_D0) & 0xFFFF,
            self._word(ctx.cpu.r_reg(REG_D1)),
            width,
            height,
        )
        self._queue_template(
            ctx,
            rp,
            self._word(ctx.cpu.r_reg(REG_D2)),
            self._word(ctx.cpu.r_reg(REG_D3)),
            width,
            height,
            pixels,
        )

    def WaitBlit(self, ctx):
        for backing in self.rp_graphics_map.values():
            ctx.exec_lib.intuition_lib._flush_batch(backing)

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

        x = ctx.cpu.r_reg(REG_D0) & 0xFFFF
        y = ctx.cpu.r_reg(REG_D1) & 0xFFFF

        if x & 0x8000:
            x -= 0x10000
        if y & 0x8000:
            y -= 0x10000

        start_x = rp.cp_x.get()
        start_y = rp.cp_y.get()

        color = self._pen_color(ctx, rp, rp.FgPen.get())
        draw_mode = rp.DrawMode.get()

        rp_graphics.batch.add(
            BFDraw(
                start_x, start_y, x, y, color, draw_mode, self._raster_state(ctx, rp)
            )
        )

        rp.cp_x.set(x)
        rp.cp_y.set(y)

    def RectFill(self, ctx):
        rastport_addr = ctx.cpu.r_reg(REG_A1)
        rp = RastPortStruct(ctx.mem, rastport_addr)
        rp_graphics = self.get_rp_graphics(rastport_addr)

        x1 = ctx.cpu.r_reg(REG_D0) & 0xFFFF
        y1 = ctx.cpu.r_reg(REG_D1) & 0xFFFF
        x2 = ctx.cpu.r_reg(REG_D2) & 0xFFFF
        y2 = ctx.cpu.r_reg(REG_D3) & 0xFFFF

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

        rp_graphics.batch.add(
            BFRectFill(left, top, w, h, color, draw_mode, self._raster_state(ctx, rp))
        )

    def SetAPen(self, ctx):
        rastport_addr = ctx.cpu.r_reg(REG_A1)
        pen = ctx.cpu.r_reg(REG_D0) & 0xFF
        if pen >= 0x80:
            pen -= 0x100

        rp = RastPortStruct(ctx.mem, rastport_addr)
        rp.FgPen.set(pen)

    def SetBPen(self, ctx):
        rp = RastPortStruct(ctx.mem, ctx.cpu.r_reg(REG_A1))
        rp.BgPen.val = ((ctx.cpu.r_reg(REG_D0) + 128) & 255) - 128

    def SetRGB4(self, ctx):

        vp = ctx.cpu.r_reg(REG_A0)
        palette = self.screen_palettes.get(vp)
        if palette is None:
            return
        index = ctx.cpu.r_reg(REG_D0) & 0xFFFF
        if index >= len(palette):
            return
        color_map = ctx.mem.r32(vp + 4) if vp else 0
        if color_map in self._color_maps:
            self.SetRGB32CM(ctx, color_map, index,
                           *((ctx.cpu.r_reg(reg) & 15) * 0x11111111
                             for reg in (REG_D1, REG_D2, REG_D3)))
            return
        palette[index] = Color(
            (ctx.cpu.r_reg(REG_D1) & 15) * 17,
            (ctx.cpu.r_reg(REG_D2) & 15) * 17,
            (ctx.cpu.r_reg(REG_D3) & 15) * 17,
            255,
        )
        for rp_addr, backing in self.rp_graphics_map.items():
            if getattr(backing, "palette", None) is palette:
                backing.surface.dirty = True
                self.invalidate(ctx, rp_addr)

    def SetDrMd(self, ctx):
        rastport_addr = ctx.cpu.r_reg(REG_A1)
        mode = ctx.cpu.r_reg(REG_D0) & 0xFF

        rp = RastPortStruct(ctx.mem, rastport_addr)
        rp.DrawMode.set(mode)

    # ---------------------------------------------------------------------
    # Helper: queue a refresh
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
        rect_addr = ctx.cpu.r_reg(REG_A1)

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
        src_region_addr = cpu.r_reg(REG_A0)
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
        bounds = (
            min(r[0] for r in rects),
            min(r[1] for r in rects),
            max(r[2] for r in rects),
            max(r[3] for r in rects),
        )
        with ExitStack() as rollback:
            nodes = []
            for left, top, right, bottom in rects:
                memory = ctx.alloc.alloc_memory(
                    RegionRectangleStruct.get_size(),
                    label="Region rectangle",
                    except_on_failure=False,
                )
                if memory is None:
                    return 0
                rollback.callback(ctx.alloc.free_memory, memory)
                ctx.mem.clear_block(memory.addr, memory.size, 0)
                node = RegionRectangleStruct(ctx.mem, memory.addr)
                self._write_bounds(
                    node.bounds,
                    (
                        left - bounds[0],
                        top - bounds[1],
                        right - bounds[0],
                        bottom - bounds[1],
                    ),
                )
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
        return self._replace_region(
            ctx, region_addr, self._region_rects(ctx, region_addr) + [rect]
        )

    def _or_region_region(self, ctx, src_region_addr, dest_region_addr):
        if not src_region_addr or not dest_region_addr:
            return 0
        if src_region_addr == dest_region_addr:
            return 1
        return self._replace_region(
            ctx,
            dest_region_addr,
            self._region_rects(ctx, dest_region_addr)
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

    def _get_damage_clip_rects_for_rp(self, ctx, rastport_addr):

        intuition = ctx.exec_lib.intuition_lib
        window_addr = intuition.rp_2_win_addr.get(rastport_addr)
        if window_addr is None:
            return None
        layer_addr = WindowStruct(ctx.mem, window_addr).WLayer.val
        if not layer_addr:
            return None
        damage = LayerStruct(ctx.mem, layer_addr).DamageList.val
        if not damage:
            return None
        return [
            Rect(a, b, c - a + 1, d - b + 1)
            for a, b, c, d in self._region_rects(ctx, damage)
        ]

    def _get_damage_clip_rect_for_rp(self, ctx, rastport_addr):
        """
        Resolve the DamageList Region for this RastPort and
        return an Rect (or None if no clipping).
        """

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

        # Clamp to non-negative dimensions
        if w <= 0 or h <= 0:
            return None

        return Rect(minx, miny, w, h)


class RastPortGraphics:
    def __init__(self, window, frame, width, height):
        self.window_id = window.id
        self.frame = frame
        self.width = width
        self.height = height
        self.batch = RPBatch()
        self.clip_rect = None
        self.clip_rects = None
        self.surface = RasterSurface(width, height)
        self.present_pending = True


def create_amiga_palette():

    palette = {}

    wb2_colors = [
        (168, 168, 168),  # 4: Amiga Gray (our default bg)
        (0x00, 0x00, 0x00),  # 0: Black
        (0xFF, 0xFF, 0xFF),  # 1: White
        (0x88, 0xAA, 0xFF),  # 2: Light Blue
        (0x00, 0x66, 0xAA),  # 3: Dark Blue
        (0x66, 0x66, 0x66),  # 5: Dark Gray
        (0xFF, 0xAA, 0x00),  # 6: Orange
        (0xAA, 0x00, 0x00),  # 7: Red
    ]

    for i in range(8):
        r, g, b = wb2_colors[i]
        palette[i] = Color(r, g, b, 255)

    for i in range(8, 32):
        r = ((i >> 0) & 0x03) * 85
        g = ((i >> 2) & 0x03) * 85
        b = ((i >> 4) & 0x03) * 85
        palette[i] = Color(r, g, b, 255)

    # Eight-plane bitmaps may address every byte-valued pen.
    for i in range(32, 256):
        palette[i] = Color(
            ((i >> 5) & 7) * 255 // 7,
            ((i >> 2) & 7) * 255 // 7,
            (i & 3) * 85,
            255,
        )

    return palette


class RPBatch:
    def __init__(self):
        self.rectfills = []
        self.draws = []
        self.texts = []
        self.commands = []

    def add(self, command):
        self.commands.append(command)
        if isinstance(command, BFText):
            self.texts.append(command)
        elif isinstance(command, BFDraw):
            self.draws.append(command)
        else:
            self.rectfills.append(command)

    def clear(self):
        self.rectfills.clear()
        self.draws.clear()
        self.texts.clear()
        commands, self.commands = self.commands, []
        with ExitStack() as cleanup:
            for command in commands:
                release = getattr(command, "release", None)
                if release is not None:
                    cleanup.callback(release)


@dataclass
class BFRectFill:
    x: int
    y: int
    w: int
    h: int
    color: "Color"
    draw_mode: int
    state: object = None


@dataclass
class BFTemplate:
    x: int
    y: int
    w: int
    h: int
    pixels: bytes
    state: object


@dataclass
class BFDraw:
    x1: int
    y1: int
    x2: int
    y2: int
    color: "Color"
    draw_mode: int
    state: object = None


@dataclass
class BFText:
    x: int
    y: int
    string: str
    font: object
    fg: "Color"
    bg: "Color"
    draw_mode: int
    release: object = None
    state: object = None
