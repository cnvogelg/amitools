"""Allocated ASL file/font requesters with explicit acceptance/cancellation."""

from amitools.vamos.libcore import LibImpl
from amitools.vamos.libtypes import TagList

from amitools.vamos.display import get_display

TB = 0x80080000


class AslLibrary(LibImpl):
    def setup_lib(self, ctx, base_addr):
        self.requests = {}
        self.backend = None

    def finish_lib(self, ctx):
        for addr in list(self.requests):
            self.FreeAslRequest(ctx, addr)

    def _tags(self, ctx, state, tags):
        if tags:
            incoming = dict(tag.get_tuple() for tag in TagList(ctx.mem, tags))
            text_tags = (1, 10) if state["kind"] else (1, 8, 9, 10)
            for number in text_tags:
                tag = TB + number
                if tag in incoming:
                    ptr = incoming.pop(tag)
                    state["texts"][number] = ctx.mem.r_cstr(ptr) if ptr else ""
            state["tags"].update(incoming)
        self._publish(ctx, state)

    def _string(self, ctx, state, offset, value):
        string = ctx.alloc.alloc_memory(
            len(value) + 1, label="ASL string", except_on_failure=False
        )
        if string is None:
            raise MemoryError("ASL string")
        ctx.mem.w_cstr(string.addr, value)
        old = state["strings"].get(offset)
        state["strings"][offset] = string
        ctx.mem.w32(state["block"].addr + offset, string.addr)
        if old:
            ctx.alloc.free_memory(old)

    def _publish(self, ctx, state):
        tags = state["tags"]
        addr = state["block"].addr
        font = state["kind"] == 1
        for tag, offset, default in (
            ((10, 8, "topaz.font"),)
            if font
            else ((8, 4, ""), (9, 8, ""), (10, 52, "#?"))
        ):
            value = state["texts"].get(tag, default)
            self._string(ctx, state, offset, value)
        for i, default in enumerate((20, 20, 400, 120)):
            ctx.mem.w16(
                addr + (24 if font else 22) + 2 * i,
                tags.get(TB + 3 + i, default) & 0xFFFF,
            )
        ctx.mem.w32(addr + (20 if font else 40), tags.get(TB + 52, 0))
        if font:
            ctx.mem.w16(addr + 12, tags.get(TB + 11, 8) & 0xFFFF)
            for tag, offset, default in (
                (12, 14, 0),
                (13, 15, 0),
                (14, 16, 1),
                (15, 17, 0),
                (59, 18, 0),
            ):
                ctx.mem.w8(addr + offset, tags.get(TB + tag, default) & 255)
            ctx.mem.w_block(addr + 32, ctx.mem.r_block(addr + 8, 8))

    def AllocAslRequest(self, ctx, kind, tags):
        if kind not in (0, 1):
            return 0
        block = ctx.alloc.alloc_memory(
            56 if kind == 0 else 44, label="ASL requester", except_on_failure=False
        )
        if block is None:
            return 0
        state = {"block": block, "kind": kind, "tags": {}, "strings": {}, "texts": {}}
        self.requests[block.addr] = state
        try:
            self._tags(ctx, state, tags)
        except MemoryError:
            self.FreeAslRequest(ctx, block.addr)
            return 0
        return block.addr

    def FreeAslRequest(self, ctx, addr):
        state = self.requests.pop(addr, None)
        if state:
            for string in state["strings"].values():
                ctx.alloc.free_memory(string)
            ctx.alloc.free_memory(state["block"])

    def AslRequest(self, ctx, addr, tags):
        try:
            return self._request(ctx, addr, tags)
        except MemoryError:
            return 0

    def _request(self, ctx, addr, tags):
        state = self.requests.get(addr)
        if not state:
            return 0
        self._tags(ctx, state, tags)
        opts = state["tags"]
        # These modes need richer requester UI/ABI support. Report failure,
        # rather than accepting a result that violates the caller's filter.
        if any(opts.get(TB + n) for n in (7, 45, 49, 61, 62)):
            return 0
        title = state["texts"].get(1, "Select font" if state["kind"] else "Select file")
        if state["kind"]:
            fields = [
                ("Font", ctx.mem.r_cstr(ctx.mem.r32(addr + 8))),
                ("Size", str(ctx.mem.r16(addr + 12))),
            ]
        else:
            fields = [
                ("Drawer", ctx.mem.r_cstr(ctx.mem.r32(addr + 8))),
                ("File", ctx.mem.r_cstr(ctx.mem.r32(addr + 4))),
            ]
        backend = self.backend or get_display(ctx).request_fields
        values = backend(title, fields)
        if values is None:
            return 0
        try:
            for value in values:
                value.encode("latin-1")
        except UnicodeEncodeError:
            return 0
        if state["kind"]:
            try:
                size = int(values[1])
            except ValueError:
                return 0
            if not 1 <= size <= 65535:
                return 0
            state["texts"][10] = values[0]
            state["tags"][TB + 11] = size
            self._string(ctx, state, 8, values[0])
            ctx.mem.w16(addr + 12, size)
            ctx.mem.w_block(addr + 32, ctx.mem.r_block(addr + 8, 8))
        else:
            state["texts"][9], state["texts"][8] = values
            self._string(ctx, state, 8, values[0])
            self._string(ctx, state, 4, values[1])
        return 1

    def AllocFileRequest(self, ctx):
        return self.AllocAslRequest(ctx, 0, 0)

    def FreeFileRequest(self, ctx, addr):
        self.FreeAslRequest(ctx, addr)

    def RequestFile(self, ctx, addr):
        return self.AslRequest(ctx, addr, 0)
