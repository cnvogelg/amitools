"""Host-independent bitmap fonts and Amiga monochrome strikes."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass
class FontStrike:
    locations: list
    spaces: list
    kerns: list
    modulo: int
    data: bytes


@dataclass
class BitmapFont:
    width: int
    height: int
    baseline: int
    strike: FontStrike


@lru_cache(maxsize=1)
def load_topaz_font():
    info = json.loads(
        Path(__file__).with_name("fonts").joinpath("TopazDoubleSans-8.json").read_text()
    )
    count = len(info["locations"])
    return BitmapFont(
        info["width"],
        info["height"],
        info["baseline"],
        FontStrike(
            info["locations"],
            [info["width"]] * count,
            [0] * count,
            info["modulo"],
            bytes.fromhex(info["data"]),
        ),
    )


def bitmap_font_mask(font, text):
    """Rasterize the bundled or a loaded bitmap strike without a host font API."""
    if not isinstance(font, BitmapFont):
        return 0, 0, b""
    positions = []
    advance = 0
    for char in text:
        code = ord(char)
        index = code - 32 if 32 <= code <= 255 else len(font.strike.locations) - 1
        loc = font.strike.locations[index]
        left = advance + font.strike.kerns[index]
        positions.append((left, loc))
        advance = left + font.strike.spaces[index]
    width = max(0, advance, *(left + (loc & 65535) for left, loc in positions))
    data = bytearray(width * font.height)
    for left, loc in positions:
        for y in range(font.height):
            for x in range(loc & 65535):
                if 0 <= left + x < width:
                    bit = (loc >> 16) + x
                    data[y * width + left + x] = bool(
                        font.strike.data[y * font.strike.modulo + bit // 8]
                        & (0x80 >> (bit & 7)))
    return width, font.height, bytes(data)
