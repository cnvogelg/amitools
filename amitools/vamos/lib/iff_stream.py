"""Adapt an IFF stream Hook to the parser's byte-stream interface."""

from .boopsi import call_hook


class HookStream:
    def __init__(self, ctx, iff, hook):
        self.ctx, self.iff, self.hook = ctx, iff, hook
        self.position = 0

    def command(self, command, buffer=0, size=0):
        packet = self.ctx.alloc.alloc_memory(
            12, label="IFFStreamCmd", except_on_failure=False
        )
        if packet is None:
            return -4
        try:
            mem = self.ctx.mem
            mem.w32(packet.addr, command)
            mem.w32(packet.addr + 4, buffer)
            mem.w32(packet.addr + 8, size & 0xFFFFFFFF)
            result = call_hook(self.ctx, self.hook, self.iff, packet.addr)
            return result - 0x100000000 if result & 0x80000000 else result
        finally:
            self.ctx.alloc.free_memory(packet)

    def read(self, size):
        if size == 0:
            return b""
        block = self.ctx.alloc.alloc_memory(
            size, label="IFF stream read", except_on_failure=False
        )
        if block is None:
            return -1
        try:
            if self.command(2, block.addr, size):
                return -1
            self.position += size
            return bytes(self.ctx.mem.r_block(block.addr, size))
        finally:
            self.ctx.alloc.free_memory(block)

    def write(self, data):
        if not data:
            return 0
        block = self.ctx.alloc.alloc_memory(
            len(data), label="IFF stream write", except_on_failure=False
        )
        if block is None:
            return -1
        try:
            self.ctx.mem.w_block(block.addr, data)
            if self.command(3, block.addr, len(data)):
                return -1
            self.position += len(data)
            return len(data)
        finally:
            self.ctx.alloc.free_memory(block)

    def tell(self):
        return self.position

    def seek(self, position, whence):
        delta = position - self.position if whence == 0 else position
        if delta and self.command(4, size=delta):
            return -1
        self.position += delta
        return self.position
