"""Host-independent windows, events and framebuffer presentation.

Backends own host resources. Amiga libraries supply indexed guest pixels and
palettes, never SDL objects. Window IDs are stable and must not be reused while
queued events may refer to them. Coordinates are host pixels; Intuition applies
its configured scale. Events carry both raw and text key interpretations.
"""

from dataclasses import dataclass


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass
class Color:
    r: int
    g: int
    b: int
    a: int = 255


@dataclass
class Event:
    kind: str
    window_id: int = 0
    x: int = 0
    y: int = 0
    button: int = 0
    raw_key: object = None
    text_key: object = None


@dataclass
class Window:
    id: int
    title: str
    width: int
    height: int
    resizable: bool = False
    frame: object = None


class Frame:
    """One RGBA presentation buffer, independent of guest bitmap storage.

    Allocate a replacement before swapping guest resources on resize. upload()
    copies the indexed frame; begin()/menu_item()/present() compose decorations
    without changing guest memory. close() releases only this frame.
    """

    def __init__(self, display, window, width, height):
        self.display, self.window = display, window
        self.width, self.height = width, height
        self.rgba = bytes((168, 168, 168, 255)) * (width * height)
        self.overlay = None

    def replacement(self, width, height):
        return self.display.create_frame(self.window, width, height)

    def upload(self, pixels, palette):
        colors = [
            bytes((palette[i].r, palette[i].g, palette[i].b, 255)) for i in range(256)
        ]
        self.rgba = b"".join(colors[pixel] for pixel in pixels)

    def begin(self):
        self.overlay = None

    def menu_item(self, font, text, x, y, w, h, enabled, hovered, checked, shortcut):
        if self.overlay is None:
            self.overlay = bytearray(self.rgba)
        bg = (
            (96, 96, 96)
            if not enabled
            else ((255, 255, 255) if hovered else (32, 32, 32))
        )
        fg = (
            (160, 160, 160)
            if not enabled
            else ((0, 0, 0) if hovered else (222, 222, 222))
        )

        def pixel(px, py, rgb):
            if 0 <= px < self.width and 0 <= py < self.height:
                offset = (py * self.width + px) * 4
                self.overlay[offset : offset + 4] = bytes((*rgb, 255))

        for py in range(max(0, y), min(self.height, y + h)):
            for px in range(max(0, x), min(self.width, x + w)):
                pixel(px, py, bg)
        if checked:
            for n in range(5):
                pixel(x + 4 + n, y + 8 + n, (0, 0, 0))
            for n in range(9):
                pixel(x + 8 + n * 6 // 8, y + 12 - n, (0, 0, 0))
        for string, right in ((text, False), (shortcut, True)):
            if not string:
                continue
            width, height, bits = self.display.font_mask(font, string)
            left = x + w - width - 4 if right else x + 16
            for py in range(height):
                for px in range(width):
                    if bits[py * width + px]:
                        pixel(left + px, y + 2 + py, fg)

    def present(self, scale=(1, 1)):
        raise NotImplementedError

    def finish(self):
        """Save an offline final frame before resources are released."""

    def close(self):
        pass


class Display:
    """Backend contract. poll() is bounded even under an event flood.

    Interactive backends may wait at most wait_ms for an event. Offline
    backends return immediately and may synthesize close requests at idle.
    """

    interactive = False

    def __init__(self):
        self.windows = {}
        self.next_id = 1

    def open(self):
        return True

    def close(self):
        for window in tuple(self.windows.values()):
            self.close_window(window)

    def create_window(self, title, width, height, resizable=False):
        window = Window(self.next_id, title, width, height, resizable)
        self.next_id += 1
        self.windows[window.id] = window
        return window

    def close_window(self, window):
        self.windows.pop(window.id, None)

    def resize_window(self, window, width, height):
        window.width, window.height = width, height

    def poll(self, wait_ms=0, limit=64):
        return []

    def open_fonts(self):
        return True

    def close_fonts(self):
        pass

    def open_font(self, path, height, style):
        return None

    def close_font(self, font):
        pass

    def font_mask(self, font, text):
        from ..lib.graphics_font import bitmap_font_mask

        return bitmap_font_mask(font, text)

    def text_size(self, font, text):
        width, height, _ = self.font_mask(font, text)
        return width, height
