"""Diskfont entry points backed by vamos' guest TextFont storage."""

import struct
from pathlib import Path

from amitools.vamos.libcore import LibImpl

from .diskfont import read_contents, read_disk_font
from .graphics import TextAttrStruct
from .intuition import TextFontStruct


class DiskfontLibrary(LibImpl):
    def setup_lib(self, ctx, base_addr):
        self.graphics_addr = ctx.lib_mgr.open_lib("graphics.library")
        self.graphics = ctx.lib_mgr.get_vlib_by_addr(self.graphics_addr).get_impl()
        self.controls = {}

    def finish_lib(self, ctx):
        ctx.lib_mgr.close_lib(self.graphics_addr)

    def OpenDiskFont(self, ctx, attr):
        if not attr:
            return 0
        ta = TextAttrStruct(ctx.mem, attr)
        name = ctx.mem.r_cstr(ta.ta_Name.val) if ta.ta_Name.val else "topaz.font"
        if name.lower() == "topaz.font" and ta.ta_YSize.val == 8:
            return self.graphics._open_font(ctx, attr)
        path = ctx.path_mgr.ami_to_sys_path(
            ctx.dos_lib.get_current_dir(ctx),
            name if ":" in name else "FONTS:" + name,
            searchMulti=True,
        )
        try:
            if path and Path(path).is_file():
                entries = read_contents(Path(path).read_bytes())
                if not entries:
                    return 0
                filename, _height, style, flags = min(
                    entries,
                    key=lambda e: (
                        abs(e[1] - ta.ta_YSize.val),
                        e[2] != ta.ta_Style.val,
                    ),
                )
                path = Path(path).parent / filename
            elif name.lower() == "topaz.font" and ta.ta_YSize.val == 16:
                path = Path(__file__).with_name("fonts") / "TopazDoubleSans-16.hunk"
            else:
                return 0
            font, style, flags = read_disk_font(path)
            addr = self.graphics._store_font(
                ctx, font, name, font.height, font.baseline, font.width, font.strike
            )
            if addr:
                tf = TextFontStruct(ctx.mem, addr)
                tf.tf_Style.val = style & ~0x80
                tf.tf_Flags.val = (flags | 2) & ~1
            return addr
        except (OSError, ValueError, struct.error):
            return 0

    def AvailFonts(self, ctx, buffer, size, flags):
        entries = [("topaz.font", 8, 0, 0x41, 1)] if flags & 1 else []
        if flags & 2:
            path = ctx.path_mgr.ami_to_sys_path(None, "FONTS:", searchMulti=True)
            if path:
                for font_file in sorted(Path(path).glob("*.font")):
                    try:
                        contents = read_contents(font_file.read_bytes())
                    except (OSError, ValueError):
                        continue
                    entries.extend(
                        (font_file.name, height, style & ~0x80, fflags, 2)
                        for filename, height, style, fflags in contents
                    )
        stride = 14 if flags & 0x10000 else 10
        needed = 2 + len(entries) * stride + sum(len(e[0]) + 1 for e in entries)
        if size < needed:
            if buffer and size >= 2:
                ctx.mem.w16(buffer, 0)
            return needed - size
        if not buffer:
            return needed
        ctx.mem.w16(buffer, len(entries))
        strings = buffer + 2 + len(entries) * stride
        for index, (name, height, style, fflags, kind) in enumerate(entries):
            entry = buffer + 2 + index * stride
            ctx.mem.w16(entry, kind)
            ctx.mem.w32(entry + 2, strings)
            ctx.mem.w16(entry + 6, height)
            ctx.mem.w8(entry + 8, style)
            ctx.mem.w8(entry + 9, fflags)
            if stride == 14:
                ctx.mem.w32(entry + 10, 0)
            ctx.mem.w_cstr(strings, name)
            strings += len(name) + 1
        return 0

    def GetDiskFontCtrl(self, ctx, tag):
        return self.controls.get(tag, 0)

    def SetDiskFontCtrlA(self, ctx, tags):
        from amitools.vamos.libtypes import TagList

        if tags:
            self.controls.update(tag.get_tuple() for tag in TagList(ctx.mem, tags))
