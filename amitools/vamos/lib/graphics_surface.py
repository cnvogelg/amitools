"""Indexed raster operations shared by the SDL backing and guest planes."""

from dataclasses import dataclass, replace


@dataclass
class RasterState:
    mem: object
    planes: tuple
    stride: int
    mask: int
    foreground: int
    background: int
    mode: int
    pattern: int
    spacing: int


class RasterSurface:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.pixels = bytearray(width * height)
        self.dirty = False

    def load(self, state):
        planes = [
            bytes(state.mem.r_block(addr, state.stride * self.height)) if addr else None
            for addr in state.planes
        ]
        before = bytes(self.pixels)
        for y in range(self.height):
            for x in range(self.width):
                offset, bit = y * state.stride + x // 8, 0x80 >> (x & 7)
                self.pixels[y * self.width + x] = sum(
                    (1 << plane)
                    for plane, data in enumerate(planes)
                    if data is not None and data[offset] & bit
                )
        self.dirty |= before != self.pixels

    def paint(self, state, x, y, bit=True, clip=None):
        if not 0 <= x < self.width or not 0 <= y < self.height:
            return
        if clip is not None and not (
            clip.x <= x < clip.x + clip.w and clip.y <= y < clip.y + clip.h
        ):
            return
        bit = bool(bit) != bool(state.mode & 4)
        mode = state.mode & 3
        if not bit and mode != 1:
            return
        index = y * self.width + x
        old = self.pixels[index]
        if mode & 2:
            value = old ^ state.mask
        else:
            pen = state.foreground if bit else state.background
            value = (old & ~state.mask) | (pen & state.mask)
        self.dirty |= old != value
        self.pixels[index] = value
        byte_addr, bit_mask = y * state.stride + x // 8, 0x80 >> (x & 7)
        for plane, address in enumerate(state.planes):
            if address and state.mask & (1 << plane):
                previous = state.mem.r8(address + byte_addr)
                byte = (
                    previous | bit_mask
                    if value & (1 << plane)
                    else previous & ~bit_mask
                )
                state.mem.w8(address + byte_addr, byte)

    def fill(self, state, left, top, width, height, clip=None):
        for y in range(max(0, top), min(self.height, top + height)):
            for x in range(max(0, left), min(self.width, left + width)):
                self.paint(state, x, y, clip=clip)

    def line(self, state, x, y, end_x, end_y, clip=None):
        dx, dy = abs(end_x - x), -abs(end_y - y)
        step_x, step_y = 1 if x < end_x else -1, 1 if y < end_y else -1
        error, count = dx + dy, 0
        while True:
            self.paint(state, x, y, state.pattern & (0x8000 >> (count & 15)), clip)
            if x == end_x and y == end_y:
                break
            twice = 2 * error
            if twice >= dy:
                error += dy
                x += step_x
            if twice <= dx:
                error += dx
                y += step_y
            count += 1

    def scroll(self, state, left, top, right, bottom, dx, dy):
        source = bytes(self.pixels)
        # Scrolling replaces pixels using the background pen for newly
        # exposed positions; drawing mode and line pattern do not apply.
        state = replace(state, mode=0)
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                sx, sy = x + dx, y + dy
                value = (
                    source[sy * self.width + sx]
                    if (left <= sx <= right and top <= sy <= bottom)
                    else state.background
                )
                state.foreground = value
                self.paint(state, x, y)
