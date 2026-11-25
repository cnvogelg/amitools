"""Guest bitmap and color-map storage for the indexed graphics backend."""

from contextlib import ExitStack
from dataclasses import dataclass

from amitools.vamos.display.base import Color
from amitools.vamos.libtypes import TagList

from .graphics import BitMapStruct, RastPortStruct
from .graphics_surface import RasterSurface
from .intuition import TextFontStruct


@dataclass
class BitmapBlit:
    x: int
    y: int
    w: int
    h: int
    pixels: bytes
    mask: bytes
    state: object


class GraphicsSupport:
    def BltMaskBitMapRastPort(
        self,
        ctx,
        srcBitMap,
        xSrc,
        ySrc,
        destRP,
        xDest,
        yDest,
        xSize,
        ySize,
        minterm,
        bltMask,
    ):
        # The API defines E0 (copy) and 20 (invert), unlike BltBitMap's
        # general three-input truth table. Mask-zero pixels are untouched.
        if not srcBitMap or not bltMask or minterm & 255 not in (0xE0, 0x20):
            return
        source = BitMapStruct(ctx.mem, srcBitMap)
        port = RastPortStruct(ctx.mem, destRP)
        state = self._raster_state(ctx, port)
        if state is None:
            return
        xSrc, ySrc, xDest, yDest, xSize, ySize = map(
            self._word, (xSrc, ySrc, xDest, yDest, xSize, ySize)
        )
        if xSize <= 0 or ySize <= 0:
            return
        for address, backing in self.rp_graphics_map.items():
            if RastPortStruct(ctx.mem, address).BitMap.val == srcBitMap:
                ctx.exec_lib.intuition_lib._flush_batch(backing)
        pixels, mask = bytearray(xSize * ySize), bytearray(xSize * ySize)
        depth = min(source.Depth.val, len(state.planes), 8)
        for y in range(ySize):
            sy = ySrc + y
            if not 0 <= sy < source.Rows.val:
                continue
            for x in range(xSize):
                sx = xSrc + x
                if not 0 <= sx < source.BytesPerRow.val * 8:
                    continue
                offset, bit = sy * source.BytesPerRow.val + sx // 8, 0x80 >> (sx & 7)
                i = y * xSize + x
                if not ctx.mem.r8(bltMask + offset) & bit:
                    continue
                mask[i] = 1
                for plane in range(depth):
                    addr = source.Planes[plane].val
                    if addr == 0xFFFFFFFF or addr and ctx.mem.r8(addr + offset) & bit:
                        pixels[i] |= 1 << plane
                if minterm & 255 == 0x20:
                    pixels[i] ^= (1 << depth) - 1
        state.mask &= (1 << depth) - 1
        command = BitmapBlit(
            xDest, yDest, xSize, ySize, bytes(pixels), bytes(mask), state
        )
        backing = self.rp_graphics_map.get(destRP)
        if backing is not None:
            backing.batch.add(command)
        else:
            bitmap = BitMapStruct(ctx.mem, port.BitMap.val)
            surface = RasterSurface(bitmap.BytesPerRow.val * 8, bitmap.Rows.val)
            surface.load(state)
            surface.bitmap_blit(state, xDest, yDest, xSize, ySize, pixels, mask)

    def GetAPen(self, ctx, rp):
        return RastPortStruct(ctx.mem, rp).FgPen.val & 255

    def GetBPen(self, ctx, rp):
        return RastPortStruct(ctx.mem, rp).BgPen.val & 255

    def GetDrMd(self, ctx, rp):
        return RastPortStruct(ctx.mem, rp).DrawMode.val & 255

    def SetABPenDrMd(self, ctx, rp, apen, bpen, drawmode):
        port = RastPortStruct(ctx.mem, rp)
        port.FgPen.val = ((apen + 128) & 255) - 128
        port.BgPen.val = ((bpen + 128) & 255) - 128
        port.DrawMode.val = drawmode & 7

    def _text_metrics(self, ctx, port, string, count, direction=1):
        font = TextFontStruct(ctx.mem, port.Font.val)
        position, left, right = 0, 0, -1
        for i in range(count & 0xFFFF):
            char = ctx.mem.r8(string + i * direction)
            index = char - font.tf_LoChar.val
            if not 0 <= index <= font.tf_HiChar.val - font.tf_LoChar.val:
                index = font.tf_HiChar.val - font.tf_LoChar.val + 1
            kern, space = 0, font.tf_XSize.val
            if font.tf_Flags.val & 0x20:
                if font.tf_CharKern.val:
                    kern = self._word(ctx.mem.r16(font.tf_CharKern.val + index * 2))
                if font.tf_CharSpace.val:
                    space = self._word(ctx.mem.r16(font.tf_CharSpace.val + index * 2))
            ink = (
                ctx.mem.r16(font.tf_CharLoc.val + index * 4 + 2)
                if font.tf_CharLoc.val
                else space
            )
            left = min(left, position + kern)
            right = max(right, position + kern + ink - 1)
            position += kern + space + port.TxSpacing.val
            yield (
                position,
                font.tf_YSize.val,
                left,
                -font.tf_Baseline.val,
                right,
                font.tf_YSize.val - font.tf_Baseline.val - 1,
            )

    @staticmethod
    def _write_extent(ctx, address, extent):
        if address:
            for i, value in enumerate(extent):
                ctx.mem.w16(address + i * 2, value & 0xFFFF)

    def TextExtent(self, ctx, rp, string, count, textExtent):
        port = RastPortStruct(ctx.mem, rp)
        extent = (0, 0, 0, 0, -1, -1)
        for extent in self._text_metrics(ctx, port, string, count):
            pass
        self._write_extent(ctx, textExtent, extent)

    def TextFit(
        self,
        ctx,
        rp,
        string,
        strLen,
        textExtent,
        constrainingExtent,
        strDirection,
        constrainingBitWidth,
        constrainingBitHeight,
    ):
        port = RastPortStruct(ctx.mem, rp)
        direction = -1 if strDirection & 0x8000 else 1
        constrainingBitWidth &= 0xFFFF
        constrainingBitHeight &= 0xFFFF
        accepted, count = (0, 0, 0, 0, -1, -1), 0
        bounds = None
        if constrainingExtent:
            bounds = tuple(
                self._word(ctx.mem.r16(constrainingExtent + 4 + i * 2))
                for i in range(4)
            )
        for extent in self._text_metrics(ctx, port, string, strLen, direction):
            width, height, left, top, right, bottom = extent
            if (
                width < 0
                or max(width, right + 1) - min(0, left) > constrainingBitWidth
                or height > constrainingBitHeight
            ):
                break
            if bounds and (
                left < bounds[0]
                or top < bounds[1]
                or right > bounds[2]
                or bottom > bounds[3]
            ):
                break
            if constrainingExtent and (
                width > ctx.mem.r16(constrainingExtent)
                or height > ctx.mem.r16(constrainingExtent + 2)
            ):
                break
            accepted, count = extent, count + 1
        self._write_extent(ctx, textExtent, accepted)
        return count

    def WritePixel(self, ctx, rp, x, y):
        port = RastPortStruct(ctx.mem, rp)
        if not port.BitMap.val:
            return 0xFFFFFFFF
        bm = BitMapStruct(ctx.mem, port.BitMap.val)
        x, y = self._word(x), self._word(y)
        if not (0 <= x < bm.BytesPerRow.val * 8 and 0 <= y < bm.Rows.val):
            return 0xFFFFFFFF
        if rp in self.rp_graphics_map:
            # Preserve ordering with rectangles/text in a window.
            self._queue_template(ctx, port, x, y, 1, 1, b"\x01")
        else:
            # Do not decode an entire offscreen bitmap for every pixel.
            offset, bit = y * bm.BytesPerRow.val + x // 8, 0x80 >> (x & 7)
            mode = port.DrawMode.val & 3
            inverted = bool(port.DrawMode.val & 4)
            if not inverted or mode == 1:
                pen = port.BgPen.val if inverted else port.FgPen.val
                for plane in range(min(bm.Depth.val, 8)):
                    address = bm.Planes[plane].val
                    if address and port.Mask.val & (1 << plane):
                        previous = ctx.mem.r8(address + offset)
                        value = (
                            previous ^ bit
                            if mode & 2
                            else (
                                previous | bit
                                if pen & (1 << plane)
                                else previous & ~bit
                            )
                        )
                        ctx.mem.w8(address + offset, value)
        return 0

    def GetBitMapAttr(self, ctx, bm, attrnum):
        if not bm:
            return 0
        bitmap = BitMapStruct(ctx.mem, bm)
        return {
            0: bitmap.Rows.val,
            4: bitmap.Depth.val,
            8: bitmap.BytesPerRow.val * 8,
            12: bitmap.Flags.val,
        }.get(attrnum, 0)

    def AllocBitMap(self, ctx, sizex, sizey, depth, flags, friend_bitmap):
        with ExitStack() as rollback:
            memory = ctx.alloc.alloc_memory(
                BitMapStruct.get_size(),
                label="Graphics bitmap",
                except_on_failure=False,
            )
            if memory is None:
                return 0
            rollback.callback(ctx.alloc.free_memory, memory)
            if not self.init_bitmap_canonical(ctx, memory.addr, sizex, sizey, depth):
                return 0
            bitmap = BitMapStruct(ctx.mem, memory.addr)
            size = bitmap.BytesPerRow.val * sizey
            for i in range(depth):
                rollback.callback(ctx.alloc.free_mem, bitmap.Planes[i].val, size)
            # Software planar storage cannot promise interleaving/display DMA.
            bitmap.Flags.val = flags & 1
            self._bitmaps[memory.addr] = rollback.pop_all()
            return memory.addr

    def FreeBitMap(self, ctx, bm):
        owned = self._bitmaps.pop(bm, None)
        if owned:
            owned.close()

    def GetColorMap(self, ctx, entries):
        if not 0 < entries <= 256:
            return 0
        memory = ctx.alloc.alloc_memory(
            52 + entries * 4, label="Graphics ColorMap", except_on_failure=False
        )
        if memory is None:
            return 0
        addr = memory.addr
        ctx.mem.clear_block(addr, memory.size, 0)
        ctx.mem.w8(addr + 1, 1)  # V39 map with low color bits
        ctx.mem.w16(addr + 2, entries)
        ctx.mem.w32(addr + 4, addr + 52)
        ctx.mem.w32(addr + 12, addr + 52 + entries * 2)
        self._color_maps[addr] = memory
        return addr

    def FreeColorMap(self, ctx, colorMap):
        owned = self._color_maps.pop(colorMap, None)
        if owned:
            ctx.alloc.free_memory(owned)
        self._pen_refs.pop(colorMap, None)
        self._color_palettes.pop(colorMap, None)

    def _color(self, ctx, cm, n):
        if not cm or n >= ctx.mem.r16(cm + 2):
            return None
        high = ctx.mem.r16(ctx.mem.r32(cm + 4) + n * 2)
        low_table = ctx.mem.r32(cm + 12) if ctx.mem.r8(cm + 1) else 0
        low = ctx.mem.r16(low_table + n * 2) if low_table else high
        return tuple(
            (((high >> shift) & 15) * 16 + ((low >> shift) & 15)) * 0x01010101
            for shift in (8, 4, 0)
        )

    def SetRGB32CM(self, ctx, cm, n, r, g, b):
        if not cm or n >= ctx.mem.r16(cm + 2):
            return
        rgb = (r >> 24, g >> 24, b >> 24)
        high = sum((c >> 4) << shift for c, shift in zip(rgb, (8, 4, 0)))
        low = sum((c & 15) << shift for c, shift in zip(rgb, (8, 4, 0)))
        ctx.mem.w16(ctx.mem.r32(cm + 4) + n * 2, high)
        low_table = ctx.mem.r32(cm + 12) if ctx.mem.r8(cm + 1) else 0
        if low_table:
            ctx.mem.w16(low_table + n * 2, low)
        palette = self._color_palettes.get(cm)
        if palette is not None:
            palette[n] = Color(*rgb, 255)
            for rp_addr, backing in self.rp_graphics_map.items():
                if getattr(backing, "palette", None) is palette:
                    backing.surface.dirty = True
                    self.invalidate(ctx, rp_addr)

    def SetRGB32(self, ctx, vp, n, r, g, b):
        if vp:
            self.SetRGB32CM(ctx, ctx.mem.r32(vp + 4), n, r, g, b)

    def GetRGB32(self, ctx, cm, firstcolor, ncolors, table):
        for i in range(ncolors):
            color = self._color(ctx, cm, firstcolor + i) or (0, 0, 0)
            for j, value in enumerate(color):
                ctx.mem.w32(table + i * 12 + j * 4, value)

    def GetRGB4(self, ctx, colorMap, entry):
        if not colorMap or entry >= ctx.mem.r16(colorMap + 2):
            return 0xFFFFFFFF
        return ctx.mem.r16(ctx.mem.r32(colorMap + 4) + entry * 2) & 0xFFF

    def FindColor(self, ctx, cm, r, g, b, maxcolor):
        if not cm:
            return 0xFFFFFFFF
        count = ctx.mem.r16(cm + 2)
        if maxcolor != 0xFFFFFFFF:
            count = min(count, maxcolor + 1)
        if not count:
            return 0xFFFFFFFF
        rgb = (r >> 24, g >> 24, b >> 24)
        return min(
            range(count),
            key=lambda n: sum(
                (a - (v >> 24)) ** 2 for a, v in zip(rgb, self._color(ctx, cm, n))
            ),
        )

    def ObtainBestPenA(self, ctx, cm, r, g, b, tags):
        # Share the nearest existing screen pen. This never changes colors
        # belonging to Intuition or another guest client.
        pen = self.FindColor(ctx, cm, r, g, b, 0xFFFFFFFF)
        options = {item.get_tag(): item.get_data() for item in TagList(ctx.mem, tags)}
        if options.get(0x84000001) and pen != 0xFFFFFFFF:
            # Fixed screen palettes cannot allocate new colors. Be
            # conservative for FailIfBad: only promise an exact match.
            actual = self._color(ctx, cm, pen)
            if tuple(c >> 24 for c in actual) != (r >> 24, g >> 24, b >> 24):
                return 0xFFFFFFFF
        if pen != 0xFFFFFFFF:
            refs = self._pen_refs.setdefault(cm, {})
            refs[pen] = refs.get(pen, 0) + 1
        return pen

    def ReleasePen(self, ctx, cm, n):
        refs = self._pen_refs.get(cm, {})
        if refs.get(n, 0):
            refs[n] -= 1
