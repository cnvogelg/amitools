"""IFF chunk streams with guest context nodes and DOS-backed I/O."""

import struct
from dataclasses import dataclass, field

from amitools.vamos.libcore import LibImpl

from .iff_stream import HookStream

CONTAINERS = {0x464F524D, 0x4C495354, 0x43415420, 0x50524F50}


@dataclass
class Chunk:
    block: object
    ident: int
    kind: int
    start: int
    size: int
    container: bool
    properties: dict = field(default_factory=dict)


@dataclass
class IFF:
    block: object
    stream: object = None
    writing: bool = False
    stack: list = field(default_factory=list)
    stops: set = field(default_factory=set)
    exits: set = field(default_factory=set)
    props: set = field(default_factory=set)
    leaving: bool = False
    done: bool = False
    dos: bool = False
    hook: int = 0


class IFFParseLibrary(LibImpl):
    def setup_lib(self, ctx, base_addr):
        self.handles = {}
        self._ctx = ctx

    def finish_lib(self, ctx):
        for addr in list(self.handles):
            self.FreeIFF(ctx, addr)

    def AllocIFF(self, ctx):
        block = ctx.alloc.alloc_memory(12, label="IFFHandle", except_on_failure=False)
        if block is None:
            return 0
        self.handles[block.addr] = IFF(block)
        return block.addr

    def InitIFFasDOS(self, ctx, addr):
        self.handles[addr].dos = True
        ctx.mem.w32(addr + 4, 6)

    def InitIFF(self, ctx, addr, flags, hook):
        self.handles[addr].dos = False
        self.handles[addr].hook = hook
        ctx.mem.w32(addr + 4, flags)

    def OpenIFF(self, ctx, addr, mode):
        state = self.handles[addr]
        if state.stream is not None:
            return -9
        if state.dos:
            fh = ctx.dos_lib.file_mgr.get_by_b_addr(ctx.mem.r32(addr))
            if not fh:
                return -5
        elif state.hook:
            fh = HookStream(ctx, addr, state.hook)
            result = fh.command(0)
            if result:
                return result
        else:
            return -11
        state.stream = fh
        state.writing = bool(mode & 1)
        state.done = state.leaving = False
        ctx.mem.w32(addr + 4, (ctx.mem.r32(addr + 4) & ~1) | (mode & 1))
        return 0

    def CloseIFF(self, ctx, addr):
        state = self.handles[addr]
        while state.stack:
            self._free_chunk(ctx, state)
        if isinstance(state.stream, HookStream):
            state.stream.command(1)
        state.stream = None
        state.stops.clear()
        state.props.clear()
        state.exits.clear()
        ctx.mem.w32(addr + 8, 0)

    def FreeIFF(self, ctx, addr):
        if addr in self.handles:
            self.CloseIFF(ctx, addr)
            ctx.alloc.free_memory(self.handles.pop(addr).block)

    def _free_chunk(self, ctx, state):
        chunk = state.stack.pop()
        for block in chunk.properties.values():
            ctx.alloc.free_memory(block)
        ctx.alloc.free_memory(chunk.block)
        ctx.mem.w32(state.block.addr + 8, len(state.stack))

    def _push(self, ctx, state, ident, kind, start, size):
        block = ctx.alloc.alloc_memory(
            24, label="IFF ContextNode", except_on_failure=False
        )
        if block is None:
            return None
        chunk = Chunk(block, ident, kind, start, size, ident in CONTAINERS)
        ctx.mem.w32(block.addr + 4, state.stack[-1].block.addr if state.stack else 0)
        ctx.mem.w32(block.addr + 8, ident)
        ctx.mem.w32(block.addr + 12, kind)
        ctx.mem.w32(block.addr + 16, size & 0xFFFFFFFF)
        state.stack.append(chunk)
        ctx.mem.w32(state.block.addr + 8, len(state.stack))
        self._scan(ctx, state)
        return chunk

    def _scan(self, ctx, state):
        pos = state.stream.tell()
        for chunk in state.stack:
            ctx.mem.w32(chunk.block.addr + 20, max(0, pos - chunk.start))

    def _skip_chunk(self, state):
        chunk = state.stack[-1]
        remaining = chunk.start + chunk.size + (chunk.size & 1) - state.stream.tell()
        if remaining < 0:
            return -8
        while remaining:
            size = min(remaining, 65536)
            data = state.stream.read(size)
            if not isinstance(data, bytes) or len(data) != size:
                return -5
            remaining -= size
        self._scan(self._ctx, state)
        return 0

    def ParseIFF(self, ctx, addr, control):
        state = self.handles[addr]
        if not state.stream or state.writing or control > 2:
            return -9
        while True:
            if state.done:
                return -1
            if state.leaving:
                chunk = state.stack[-1]
                error = self._skip_chunk(state)
                if error:
                    return error
                self._free_chunk(ctx, state)
                state.leaving = False
                if not state.stack:
                    state.done = True
                    return -1
            if state.stack:
                chunk = state.stack[-1]
                pos = state.stream.tell()
                if not chunk.container or pos == chunk.start + chunk.size:
                    state.leaving = True
                    if control or (chunk.kind, chunk.ident) in state.exits:
                        return -2
                    continue
                if pos + 8 > chunk.start + chunk.size:
                    return -8
            raw = state.stream.read(8)
            if not isinstance(raw, bytes) or len(raw) != 8:
                return -5
            ident, size = struct.unpack(">II", raw)
            start = state.stream.tell()
            if size > 0x7FFFFFFF:
                return -8
            if (
                state.stack
                and start + size + (size & 1)
                > state.stack[-1].start + state.stack[-1].size
            ):
                return -8
            if not state.stack and ident not in CONTAINERS:
                return -10
            kind = state.stack[-1].kind if state.stack else 0
            if ident in CONTAINERS:
                raw = state.stream.read(4) if size >= 4 else b""
                if not isinstance(raw, bytes) or len(raw) != 4:
                    return -8
                kind = int.from_bytes(raw, "big")
            if self._push(ctx, state, ident, kind, start, size) is None:
                return -4
            pair = (kind, ident)
            if control != 2 and pair in state.props:
                if ident in CONTAINERS:
                    return -9
                scope = next(
                    (
                        c
                        for c in reversed(state.stack[:-1])
                        if c.ident in (0x464F524D, 0x4C495354)
                    ),
                    None,
                )
                if scope is None:
                    return -3
                prop = ctx.alloc.alloc_memory(
                    8 + size, label="IFF StoredProperty", except_on_failure=False
                )
                if prop is None:
                    return -4
                raw = state.stream.read(size)
                if not isinstance(raw, bytes) or len(raw) != size:
                    ctx.alloc.free_memory(prop)
                    return -5
                old = scope.properties.pop(pair, None)
                if old:
                    ctx.alloc.free_memory(old)
                ctx.mem.w32(prop.addr, size)
                ctx.mem.w32(prop.addr + 4, prop.addr + 8)
                ctx.mem.w_block(prop.addr + 8, raw)
                scope.properties[pair] = prop
                self._scan(ctx, state)
            if control or pair in state.stops:
                return 0

    def CurrentChunk(self, ctx, addr):
        stack = self.handles[addr].stack
        return stack[-1].block.addr if stack else 0

    def ParentChunk(self, ctx, node):
        return ctx.mem.r32(node + 4) if node else 0

    def FindPropContext(self, ctx, addr):
        for chunk in reversed(self.handles[addr].stack):
            if chunk.ident in (0x464F524D, 0x4C495354):
                return chunk.block.addr
        return 0

    def StopChunk(self, ctx, addr, kind, ident):
        self.handles[addr].stops.add((kind, ident))
        return 0

    def StopOnExit(self, ctx, addr, kind, ident):
        self.handles[addr].exits.add((kind, ident))
        return 0

    def PropChunk(self, ctx, addr, kind, ident):
        self.handles[addr].props.add((kind, ident))
        return 0

    def StopChunks(self, ctx, addr, pairs, count):
        for i in range(count):
            self.StopChunk(
                ctx, addr, ctx.mem.r32(pairs + 8 * i), ctx.mem.r32(pairs + 8 * i + 4)
            )
        return 0

    def PropChunks(self, ctx, addr, pairs, count):
        for i in range(count):
            self.PropChunk(
                ctx, addr, ctx.mem.r32(pairs + 8 * i), ctx.mem.r32(pairs + 8 * i + 4)
            )
        return 0

    def FindProp(self, ctx, addr, kind, ident):
        for chunk in reversed(self.handles[addr].stack):
            prop = chunk.properties.get((kind, ident))
            if prop:
                return prop.addr
        return 0

    def ReadChunkBytes(self, ctx, addr, buffer, size):
        state = self.handles[addr]
        if not state.stack or state.writing:
            return -9
        chunk = state.stack[-1]
        size = min(size, chunk.start + chunk.size - state.stream.tell())
        data = state.stream.read(size)
        if not isinstance(data, bytes) or len(data) != size:
            return -5
        ctx.mem.w_block(buffer, data)
        self._scan(ctx, state)
        return size

    def ReadChunkRecords(self, ctx, addr, buffer, size, count):
        state = self.handles[addr]
        if not size or not state.stack:
            return -9
        chunk = state.stack[-1]
        count = min(count, (chunk.start + chunk.size - state.stream.tell()) // size)
        result = self.ReadChunkBytes(ctx, addr, buffer, size * count)
        return result if result < 0 else result // size

    def PushChunk(self, ctx, addr, kind, ident, size):
        state = self.handles[addr]
        if not state.stream or not state.writing:
            return -9
        if not state.stack and ident not in CONTAINERS:
            return -10
        if size != 0xFFFFFFFF and size > 0x7FFFFFFF:
            return -9
        if ident in CONTAINERS and size != 0xFFFFFFFF and size < 4:
            return -9
        header = struct.pack(">II", ident, 0 if size == 0xFFFFFFFF else size)
        if state.stream.write(header) != 8:
            return -6
        start = state.stream.tell()
        if ident in CONTAINERS and state.stream.write(struct.pack(">I", kind)) != 4:
            return -6
        if ident not in CONTAINERS and state.stack:
            kind = state.stack[-1].kind
        return 0 if self._push(ctx, state, ident, kind, start, size) else -4

    def WriteChunkBytes(self, ctx, addr, buffer, size):
        state = self.handles[addr]
        if not state.stack or not state.writing:
            return -9
        chunk = state.stack[-1]
        if chunk.size != 0xFFFFFFFF:
            size = min(size, max(0, chunk.start + chunk.size - state.stream.tell()))
        result = state.stream.write(ctx.mem.r_block(buffer, size))
        self._scan(ctx, state)
        return result if result >= 0 else -6

    def WriteChunkRecords(self, ctx, addr, buffer, size, count):
        state = self.handles[addr]
        if not size or not state.stack:
            return -9
        chunk = state.stack[-1]
        if chunk.size != 0xFFFFFFFF:
            count = min(
                count, max(0, chunk.start + chunk.size - state.stream.tell()) // size
            )
        result = self.WriteChunkBytes(ctx, addr, buffer, size * count)
        return result if result < 0 else result // size

    def PopChunk(self, ctx, addr):
        state = self.handles[addr]
        if not state.stack:
            return -9
        chunk = state.stack[-1]
        if state.writing:
            end = state.stream.tell()
            size = end - chunk.start
            if chunk.size not in (size, 0xFFFFFFFF):
                return -8
            if state.stream.seek(chunk.start - 4, 0) < 0:
                return -7
            if state.stream.write(struct.pack(">I", size)) != 4:
                return -6
            if state.stream.seek(end, 0) < 0:
                return -7
            if size & 1 and state.stream.write(b"\0") != 1:
                return -6
        else:
            error = self._skip_chunk(state)
            if error:
                return error
        self._free_chunk(ctx, state)
        self._scan(ctx, state)
        return 0

    def GoodID(self, ctx, ident):
        return int(all(32 <= b <= 126 for b in ident.to_bytes(4, "big")))

    def GoodType(self, ctx, kind):
        return int(
            self.GoodID(ctx, kind)
            and not any(97 <= b <= 122 for b in kind.to_bytes(4, "big"))
        )

    def IDtoStr(self, ctx, ident, buffer):
        ctx.mem.w_block(buffer, ident.to_bytes(4, "big") + b"\0")
        return buffer
