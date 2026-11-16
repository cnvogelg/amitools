"""Offline RGBA PNG snapshots using only the standard library."""

import os
import struct
import tempfile
import zlib
from pathlib import Path

from .base import Display, Event, Frame


def encode_png(width, height, rgba):
    if width <= 0 or height <= 0 or len(rgba) != width * height * 4:
        raise ValueError("invalid RGBA dimensions")

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    rows = b"".join(
        b"\0" + rgba[y * width * 4 : (y + 1) * width * 4] for y in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


class PNGFrame(Frame):
    def finish(self):
        self.present()

    def present(self, scale=(1, 1)):
        # Capture guest pixels exactly. Host window scale does not resample PNGs.
        data = encode_png(self.width, self.height, self.overlay or self.rgba)
        self.display.output.mkdir(parents=True, exist_ok=True)
        path = self.display.output / f"window-{self.window.id:04d}.png"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = stream.name
                stream.write(data)
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                os.unlink(temporary)


class PNGDisplay(Display):
    def __init__(self, output):
        super().__init__()
        self.output = Path(output)
        self.close_requested = set()

    def create_frame(self, window, width, height):
        return PNGFrame(self, window, width, height)

    def poll(self, wait_ms=0, limit=64):
        if not wait_ms:
            return []
        # Once guest drawing has settled, ask the application to close normally.
        events = []
        for window_id in self.windows:
            if window_id not in self.close_requested:
                events.append(Event("close", window_id))
                self.close_requested.add(window_id)
                if len(events) >= limit:
                    break
        return events
