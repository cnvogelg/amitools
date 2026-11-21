"""Read classic bitmap diskfont hunks into the shared strike representation."""

import struct

from amitools.binfmt.BinFmt import BinFmt
from amitools.binfmt.hunk.HunkBlockFile import HunkParseError
from amitools.binfmt.Relocate import Relocate

from .graphics_font import BitmapFont, FontStrike


def read_contents(data):
    if len(data) < 4:
        raise ValueError("Short font contents")
    kind, count = struct.unpack_from(">HH", data)
    if kind not in (0x0F00, 0x0F02) or len(data) < 4 + count * 260:
        raise ValueError("Not a bitmap font contents file")
    entries = []
    for index in range(count):
        start = 4 + index * 260
        filename = data[start : start + 254].split(b"\0", 1)[0].decode("latin-1")
        height, style, flags = struct.unpack_from(">HBB", data, start + 256)
        if filename and height:
            entries.append((filename, height, style, flags))
    return entries


def read_disk_font(path):
    try:
        image = BinFmt().load_image(str(path))
    except HunkParseError as exc:
        raise ValueError("Malformed disk font hunk") from exc
    if image is None or image.get_size() > 4 * 1024 * 1024:
        raise ValueError("Invalid disk font hunk")
    data = Relocate(image).relocate_one_block(0)
    if len(data) < 110 or struct.unpack_from(">H", data, 18)[0] != 0x0F80:
        raise ValueError("Missing DiskFontHeader")
    (
        height,
        style,
        flags,
        width,
        baseline,
        _bold,
        _accessors,
        low,
        high,
        bitmap,
        stride,
        loc,
        space,
        kern,
    ) = struct.unpack_from(">HBBHHHHBBIHIII", data, 78)
    if (
        not 0 < height <= 1024
        or not width
        or baseline >= height
        or high < low
        or style & 0x40
    ):
        raise ValueError("Unsupported disk font metrics or color font")
    count = high - low + 2

    def unpack_table(addr, code, size):
        if addr < 0 or addr + count * size > len(data):
            raise ValueError("Disk font table outside hunk")
        return struct.unpack_from(">" + code * count, data, addr)

    locations = unpack_table(loc, "I", 4)
    spaces = unpack_table(space, "h", 2) if space else [width] * count
    kerns = unpack_table(kern, "h", 2) if kern else [0] * count
    if not stride or bitmap + stride * height > len(data):
        raise ValueError("Disk font bitmap outside hunk")
    if any(
        (location >> 16) + (location & 65535) > stride * 8 for location in locations
    ):
        raise ValueError("Disk font glyph outside bitmap row")
    indices = [
        code - low if low <= code <= high else count - 1 for code in range(32, 256)
    ] + [count - 1]
    strike = FontStrike(
        [locations[i] for i in indices],
        [spaces[i] for i in indices],
        [kerns[i] for i in indices],
        stride,
        bytes(data[bitmap : bitmap + stride * height]),
    )
    return BitmapFont(width, height, baseline, strike), style, flags
