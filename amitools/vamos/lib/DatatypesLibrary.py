"""Picture datatypes exposed as real BOOPSI objects (palette ILBM)."""

from pathlib import Path

from amitools.vamos.libcore import LibImpl
from amitools.vamos.libtypes import TagList

from .boopsi import call_hook
from .picture_datatype import decode_ilbm

DTA = 0x80001000


class DatatypesLibrary(LibImpl):
    def setup_lib(self, ctx, base_addr):
        self.ctx = ctx
        self.intuition_addr = ctx.lib_mgr.open_lib("intuition.library")
        self.intuition = ctx.lib_mgr.get_vlib_by_addr(self.intuition_addr).get_impl()
        self.boopsi = self.intuition.boopsi
        self.cls = self.boopsi.make_class(None, self.boopsi.root, 0)
        self.boopsi.host_dispatchers[self.cls] = self._dispatch
        self.objects = {}

    def finish_lib(self, ctx):
        # Free host-owned payloads without dispatching into exited code.
        for obj in list(self.objects):
            self._free_payload(ctx, obj)
        self.boopsi.host_dispatchers.pop(self.cls, None)
        self.boopsi.free_class(self.cls)
        ctx.lib_mgr.close_lib(self.intuition_addr)

    def _free_payload(self, ctx, obj):
        owner = self.objects.pop(obj, None)
        if owner:
            for block in reversed(owner["blocks"]):
                ctx.alloc.free_memory(block)

    def NewDTObjectA(self, ctx, name, tags):
        attrs = dict(tag.get_tuple() for tag in TagList(ctx.mem, tags)) if tags else {}
        source = attrs.get(DTA + 101, 2)
        if attrs.get(DTA + 31, 0x70696374) != 0x70696374 or source not in (2, 5):
            return 0
        try:
            if source == 5:
                size = attrs.get(DTA + 40, 0)
                if not 0 < size <= 16 * 1024 * 1024:
                    return 0
                data = bytes(ctx.mem.r_block(attrs.get(DTA + 39, 0), size))
            else:
                if not name:
                    return 0
                path = ctx.path_mgr.ami_to_sys_path(
                    ctx.dos_lib.get_current_dir(ctx),
                    ctx.mem.r_cstr(name),
                    searchMulti=True,
                )
                if not path:
                    return 0
                data = Path(path).read_bytes()
            header, planes, mask, cmap, mode = decode_ilbm(data)
        except (OSError, ValueError):
            return 0
        obj = self.boopsi.new_object(self.cls, tags)
        if not obj:
            return 0
        owner = {
            "blocks": [],
            "attrs": {},
            "width": int.from_bytes(header[:2], "big"),
            "height": int.from_bytes(header[2:4], "big"),
            "depth": header[8],
        }
        self.objects[obj] = owner

        def store(data):
            block = ctx.alloc.alloc_memory(
                max(len(data), 1), label="picture.datatype", except_on_failure=False
            )
            if block is None:
                raise MemoryError("picture.datatype")
            owner["blocks"].append(block)
            ctx.mem.w_block(block.addr, bytes(data))
            return block.addr

        try:
            bitmap = store(bytes(40))
            stride = ((owner["width"] + 15) // 16) * 2
            ctx.mem.w16(bitmap, stride)
            ctx.mem.w16(bitmap + 2, owner["height"])
            ctx.mem.w8(bitmap + 5, owner["depth"])
            for i, plane in enumerate(planes):
                ctx.mem.w32(bitmap + 8 + i * 4, store(plane))
            colors = b"".join((c * 0x01010101).to_bytes(4, "big") for c in cmap)
            owner["attrs"] = {
                DTA + 107: owner["width"],
                DTA + 108: owner["height"],
                DTA + 200: mode,
                DTA + 201: store(header),
                DTA + 202: bitmap,
                DTA + 203: store(cmap),
                DTA + 204: store(colors),
                DTA + 209: len(cmap) // 3,
                DTA + 215: bitmap,
                DTA + 258: store(mask) if mask is not None else 0,
            }
            return obj
        except MemoryError:
            self.DisposeDTObject(ctx, obj)
            return 0
        except BaseException:
            self.DisposeDTObject(ctx, obj)
            raise

    def _dispatch(self, cls, obj, msg):
        ctx = self.ctx
        method = ctx.mem.r32(msg)
        owner = self.objects.get(obj)
        if method == 0x102:
            self._free_payload(ctx, obj)
        elif owner:
            attrs = owner["attrs"]
            if method == 0x104:
                tag = ctx.mem.r32(msg + 4)
                if tag in attrs:
                    ctx.mem.w32(ctx.mem.r32(msg + 8), attrs[tag])
                    return 1
                return 0
            if method in (0x103, 0x108):
                # These control flags do not change ownership of our original
                # bitmap. Layout is synchronous and currently has no remap.
                tags = ctx.mem.r32(msg + 4)
                if tags:
                    for tag in TagList(ctx.mem, tags):
                        if tag.get_tag() in (DTA + 211, DTA + 213):
                            attrs[tag.get_tag()] = tag.get_data()
                return 0
            if method == 0x601:
                ptr, size = ctx.mem.r32(msg + 12), ctx.mem.r32(msg + 16)
                if not ptr or size < 24:
                    return 0
                ctx.mem.clear_block(ptr, min(size, 36), 0)
                ctx.mem.w32(ptr + 12, owner["width"])
                ctx.mem.w32(ptr + 16, owner["height"])
                ctx.mem.w32(ptr + 20, owner["depth"])
                return 1
            if method in (0x602, 0x603):
                # A request to remap cannot be reported successful until
                # palette allocation and conversion are implemented.
                return int(not attrs.get(DTA + 211, 0))
        return self.boopsi.root_dispatch(cls, obj, msg)

    def DisposeDTObject(self, ctx, obj):
        self.boopsi.method(obj, 0x102)

    def GetDTAttrsA(self, ctx, obj, tags):
        if not obj or not tags:
            return 0
        return sum(
            bool(self.boopsi.method(obj, 0x104, tag.get_tag(), tag.get_data()))
            for tag in TagList(ctx.mem, tags)
        )

    def SetDTAttrsA(self, ctx, obj, window, req, tags):
        return self.boopsi.method(obj, 0x103, tags, 0)

    def DoDTMethodA(self, ctx, obj, window, req, message):
        return call_hook(ctx, ctx.mem.r32(obj - 4), obj, message) if obj else 0

    def DoAsyncLayout(self, ctx, obj, message):
        return self.DoDTMethodA(ctx, obj, 0, 0, message)
