"""Classic DiskObject files, guest image storage, and ToolTypes."""

import struct
from pathlib import Path

from amitools.icon import _format
from amitools.vamos.libcore import LibImpl


class IconLibrary(LibImpl):
    def setup_lib(self, ctx, base_addr):
        self.objects = {}

    def finish_lib(self, ctx):
        for obj in list(self.objects):
            self.FreeDiskObject(ctx, obj)

    def _path(self, ctx, name):
        return ctx.path_mgr.ami_to_sys_path(
            ctx.dos_lib.get_current_dir(ctx), name + ".info", searchMulti=True
        )

    def _error(self, ctx, code):
        ctx.dos_lib.setioerr(ctx, code)
        return 0

    def _import(self, ctx, raw):
        parsed = _format.parse_icon_data(raw, strict=True)
        owned = []

        def store(data):
            block = ctx.alloc.alloc_memory(
                max(1, len(data)), label="DiskObject data", except_on_failure=False
            )
            if block is None:
                raise MemoryError("DiskObject data")
            owned.append(block)
            ctx.mem.w_block(block.addr, bytes(data))
            return block.addr

        try:
            obj = store(parsed.data[:78])
            # Serialized pointer values are presence flags, never addresses.
            for offset in (4, 22, 26, 30, 38, 50, 54, 66, 70):
                ctx.mem.w32(obj + offset, 0)
            data = parsed.main_icons_blob
            pos = 0
            for offset in (22, 26)[: parsed.num_main_icons]:
                size = _format.get_main_icon_size(data, pos, strict=True)
                image = store(data[pos : pos + size])
                ctx.mem.w32(image + 10, image + 20)
                ctx.mem.w32(image + 16, 0)
                ctx.mem.w32(obj + offset, image)
                pos += size
            if parsed.drawerdata:
                drawer = bytearray(parsed.drawerdata + (parsed.drawerdata2 or b""))
                for offset in (18, 22, 26, 30, 34):
                    drawer[offset : offset + 4] = bytes(4)
                ctx.mem.w32(obj + 66, store(drawer))
            for offset, value in ((50, parsed.defaulttool), (70, parsed.toolwindow)):
                if value is not None:
                    ctx.mem.w32(
                        obj + offset, store(value[4:].split(b"\0", 1)[0] + b"\0")
                    )
            if parsed.has_tooltypes:
                table = store(bytes(4 * (len(parsed.tooltypes_raw_entries) + 1)))
                ctx.mem.w32(obj + 54, table)
                for index, entry in enumerate(parsed.tooltypes_raw_entries):
                    ctx.mem.w32(
                        table + 4 * index, store(entry.split(b"\0", 1)[0] + b"\0")
                    )
            self.objects[obj] = (owned, parsed.glowicons)
            return obj
        except BaseException:
            for block in reversed(owned):
                ctx.alloc.free_memory(block)
            raise

    def GetDiskObject(self, ctx, name):
        if not name:
            return 0
        path = self._path(ctx, ctx.mem.r_cstr(name))
        if not path:
            return self._error(ctx, 205)
        try:
            return self._import(ctx, Path(path).read_bytes())
        except MemoryError:
            return self._error(ctx, 103)
        except OSError:
            return self._error(ctx, 205)
        except (ValueError, IndexError, struct.error):
            return self._error(ctx, 212)

    def FreeDiskObject(self, ctx, obj):
        owner = self.objects.pop(obj, None)
        if owner:
            for block in reversed(owner[0]):
                ctx.alloc.free_memory(block)

    def FindToolType(self, ctx, table, key):
        if not table or not key:
            return 0
        key = ctx.mem.r_cstr(key).casefold()
        while ctx.mem.r32(table):
            addr = ctx.mem.r32(table)
            text = ctx.mem.r_cstr(addr)
            name, sep, _value = text.partition("=")
            if name.casefold() == key:
                return addr + len(name) + len(sep)
            table += 4
        return 0

    def MatchToolValue(self, ctx, string, value):
        if not string or not value:
            return 0
        target = ctx.mem.r_cstr(value).casefold()
        return int(
            any(
                part.strip().casefold() == target
                for part in ctx.mem.r_cstr(string).split("|")
            )
        )

    def _export(self, ctx, obj):
        mem = ctx.mem
        header = bytearray(mem.r_block(obj, 78))
        # Keep scalar fields, canonicalize every serialized pointer.
        for offset in (4, 22, 26, 30, 38, 50, 54, 66, 70):
            header[offset : offset + 4] = struct.pack(
                ">I", int(bool(mem.r32(obj + offset)))
            )
        chunks = [bytes(header)]
        drawer = mem.r32(obj + 66)
        if drawer:
            chunks.append(bytes(mem.r_block(drawer, 56)))
        for offset in (22, 26):
            image = mem.r32(obj + offset)
            if not image:
                continue
            image_header = bytearray(mem.r_block(image, 20))
            width, height, depth = struct.unpack_from(">HHH", image_header, 4)
            size = ((width + 15) // 16) * 2 * height * depth
            if depth > 8 or size > 10_000_000:
                raise ValueError("Invalid icon image")
            image_header[10:14] = struct.pack(">I", 1)
            image_header[16:20] = bytes(4)
            chunks.extend((image_header, bytes(mem.r_block(mem.r32(image + 10), size))))
        for offset in (50, 54, 70):
            ptr = mem.r32(obj + offset)
            if not ptr:
                continue
            if offset == 54:
                entries = []
                while mem.r32(ptr):
                    entries.append(mem.r_cstr(mem.r32(ptr)).encode("latin-1") + b"\0")
                    ptr += 4
                chunks.append(_format.build_tooltypes_table(entries))
            else:
                text = mem.r_cstr(ptr).encode("latin-1") + b"\0"
                chunks.extend((struct.pack(">I", len(text)), text))
        if drawer and header[47] == 1:
            chunks.append(bytes(mem.r_block(drawer + 56, 6)))
        owner = self.objects.get(obj)
        if owner and owner[1]:
            chunks.append(owner[1])
        return b"".join(chunks)

    def PutDiskObject(self, ctx, name, obj):
        if not name or not obj:
            return 0
        path = self._path(ctx, ctx.mem.r_cstr(name))
        if not path:
            return self._error(ctx, 205)
        try:
            data = self._export(ctx, obj)
            Path(path).write_bytes(data)
            return 1
        except (OSError, ValueError):
            return self._error(ctx, 212)

    def DeleteDiskObject(self, ctx, name):
        path = self._path(ctx, ctx.mem.r_cstr(name)) if name else None
        try:
            if not path:
                return self._error(ctx, 205)
            Path(path).unlink()
            return 1
        except OSError:
            return self._error(ctx, 205)

    def NewDiskObject(self, ctx, kind):
        if not 1 <= kind <= 8:
            return 0
        # A simple monochrome document image for default icons.
        header = bytearray(78)
        struct.pack_into(">HH", header, 0, 0xE310, 1)
        struct.pack_into(">HH", header, 12, 16, 16)
        struct.pack_into(">H", header, 16, 4)  # GFLG_GADGIMAGE
        struct.pack_into(">I", header, 22, 1)
        header[48] = kind
        struct.pack_into(">III", header, 58, 0x80000000, 0x80000000, 0)
        struct.pack_into(">I", header, 74, 4096)
        image = struct.pack(">hhhhhIBBI", 0, 0, 16, 16, 1, 1, 1, 0, 0)
        pixels = struct.pack(">16H", 0x7FFE, *([0x4002] * 14), 0x7FFE)
        try:
            return self._import(ctx, header + image + pixels)
        except MemoryError:
            return 0

    def GetDefDiskObject(self, ctx, kind):
        return self.NewDiskObject(ctx, kind)

    def GetDiskObjectNew(self, ctx, name):
        result = self.GetDiskObject(ctx, name)
        return result or self.GetDefDiskObject(ctx, 4)

    def GetIconTagList(self, ctx, name, tags):
        return self.GetDiskObject(ctx, name)

    def PutIconTagList(self, ctx, name, obj, tags):
        return self.PutDiskObject(ctx, name, obj)

    def DupDiskObjectA(self, ctx, obj, tags):
        if not obj:
            return 0
        try:
            return self._import(ctx, self._export(ctx, obj))
        except (ValueError, MemoryError):
            return 0
