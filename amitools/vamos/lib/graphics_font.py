"""Convert SDL fonts to the public Amiga monochrome strike format."""

import ctypes
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


def render_font_surface(font, text, foreground, background=None):
    """Host menu overlays use the same bundled bitmap as guest Text()."""
    import sdl2
    from sdl2 import sdlttf

    if not isinstance(font, BitmapFont):
        if background is None:
            return sdlttf.TTF_RenderUTF8_Solid(font, text.encode("utf-8"), foreground)
        return sdlttf.TTF_RenderUTF8_Shaded(
            font, text.encode("utf-8"), foreground, background
        )
    if not text:
        return None
    surface = sdl2.SDL_CreateRGBSurfaceWithFormat(
        0, len(text) * font.width, font.height, 32, sdl2.SDL_PIXELFORMAT_RGBA8888
    )
    if not surface:
        return None
    image = surface.contents
    fg = (foreground.r << 24) | (foreground.g << 16) | (foreground.b << 8) | 255
    bg = (
        0
        if background is None
        else ((background.r << 24) | (background.g << 16) | (background.b << 8) | 255)
    )
    for y in range(font.height):
        row = ctypes.cast(
            image.pixels + y * image.pitch, ctypes.POINTER(ctypes.c_uint32)
        )
        for n, char in enumerate(text):
            code = ord(char)
            index = code - 32 if 32 <= code <= 255 else 224
            location = font.strike.locations[index]
            for x in range(font.width):
                bit = (location >> 16) + x
                on = x < (location & 0xFFFF) and bool(
                    font.strike.data[y * font.strike.modulo + bit // 8]
                    & (0x80 >> (bit & 7))
                )
                row[n * font.width + x] = fg if on else bg
    sdl2.SDL_SetSurfaceBlendMode(surface, sdl2.SDL_BLENDMODE_BLEND)
    return surface


def open_pixel_font(path, height, style):
    """Amiga ta_YSize is a pixel height; SDL's input is a point size."""
    from sdl2 import sdlttf

    points = height
    while points > 0:
        font = sdlttf.TTF_OpenFont(path.encode("utf-8"), points)
        if not font:
            return None
        keep = False
        try:
            sdlttf.TTF_SetFontStyle(font, style)
            actual = sdlttf.TTF_FontHeight(font)
            ascent = sdlttf.TTF_FontAscent(font)
            if 0 <= ascent < actual <= height:
                keep = True
                return font
            points = min(
                points - 1, (points * height + max(actual, 1) - 1) // max(actual, 1)
            )
        finally:
            if not keep:
                sdlttf.TTF_CloseFont(font)
    return None


def read_font_strike(font, height):
    """Store Latin-1 glyphs and the mandatory extra undefined-character slot.

    CharLoc words hold bit offset and ink width. CharKern moves to the ink;
    CharSpace moves from there to the next character's origin. Each row of
    CharData has an even byte stride and uses Amiga's MSB-first bit order.
    """
    import sdl2
    from sdl2 import sdlttf

    glyphs, locations, spaces, kerns = [], [], [], []
    offset = 0
    for code in [*range(32, 256), 0xFFFD]:
        text_width, text_height = ctypes.c_int(), ctypes.c_int()
        if (
            sdlttf.TTF_SizeUTF8(
                font,
                chr(code).encode("utf-8"),
                ctypes.byref(text_width),
                ctypes.byref(text_height),
            )
            != 0
        ):
            return None
        # SDL suppresses discretionary characters such as the soft hyphen.
        # It cannot render a zero-width surface, but the slot is still valid.
        if text_width.value == 0:
            locations.append(offset << 16)
            spaces.append(0)
            kerns.append(0)
            glyphs.append([b""] * height)
            continue
        min_x, max_x, min_y, max_y, advance = (ctypes.c_int() for _ in range(5))
        if (
            sdlttf.TTF_GlyphMetrics(
                font,
                code,
                ctypes.byref(min_x),
                ctypes.byref(max_x),
                ctypes.byref(min_y),
                ctypes.byref(max_y),
                ctypes.byref(advance),
            )
            != 0
        ):
            return None
        surface = sdlttf.TTF_RenderGlyph_Solid(
            font, code, sdl2.SDL_Color(255, 255, 255, 255)
        )
        if not surface:
            return None
        try:
            image = surface.contents
            if image.format.contents.BytesPerPixel != 1:
                return None
            pixels = ctypes.string_at(image.pixels, image.pitch * image.h)
            rows = [
                pixels[y * image.pitch : y * image.pitch + image.w]
                if y < image.h
                else b""
                for y in range(height)
            ]
            columns = [x for x in range(image.w) if any(row[x] for row in rows if row)]
            left = min(columns) if columns else 0
            right = max(columns) + 1 if columns else 0
            width = right - left
            kern = left + min(0, min_x.value) if width else 0
            space = advance.value - kern
            if offset + width > 0xFFFF or not (
                -32768 <= kern <= 32767 and -32768 <= space <= 32767
            ):
                return None
            locations.append((offset << 16) | width)
            kerns.append(kern)
            spaces.append(space)
            glyphs.append([row[left:right] for row in rows])
            offset += width
        finally:
            sdl2.SDL_FreeSurface(surface)
    modulo = ((offset + 15) // 16) * 2
    data = bytearray(modulo * height)
    for location, rows in zip(locations, glyphs):
        start = location >> 16
        for y, row in enumerate(rows):
            for x, pixel in enumerate(row):
                if pixel:
                    bit = start + x
                    data[y * modulo + bit // 8] |= 0x80 >> (bit & 7)
    return FontStrike(locations, spaces, kerns, modulo, bytes(data))
