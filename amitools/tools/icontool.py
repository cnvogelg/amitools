#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple, Callable, Any, Dict

# Optional PNG support - gracefully disabled if pypng not installed
try:
    import png
    HAS_PNG = True
except ImportError:
    HAS_PNG = False

WB_DISKMAGIC = 0xE310

# Workbench 1.3 default palette (8 colors)
WB13_COLORS = [
    (0x00, 0x55, 0xAA),  # 0: blue
    (0xFF, 0xFF, 0xFF),  # 1: white
    (0x00, 0x00, 0x22),  # 2: black
    (0xFF, 0x88, 0x00),  # 3: orange
    (0x66, 0x66, 0x66),  # 4: gray
    (0xEE, 0xEE, 0xEE),  # 5: light gray
    (0xDD, 0x77, 0x44),  # 6: brown
    (0xFF, 0xEE, 0x11),  # 7: yellow
]

# Workbench 2.0+ default palette (8 colors)
WB20_COLORS = [
    (0xAA, 0xAA, 0xAA),  # 0: gray
    (0x00, 0x00, 0x00),  # 1: black
    (0xFF, 0xFF, 0xFF),  # 2: white
    (0x66, 0x88, 0xBB),  # 3: blue
    (0xEE, 0x44, 0x44),  # 4: red
    (0x55, 0xDD, 0x54),  # 5: green
    (0x00, 0x44, 0xDD),  # 6: dark blue
    (0xEE, 0x99, 0x00),  # 7: orange
]

# Extended 16-color palette for 4+ plane icons (MagicWB style)
PALETTE_16 = WB20_COLORS + [
    (0x00, 0x00, 0x00),  # 8: Black
    (0xFF, 0x00, 0x00),  # 9: Red
    (0x00, 0xFF, 0x00),  # 10: Green
    (0xFF, 0xFF, 0x00),  # 11: Yellow
    (0x00, 0x00, 0xFF),  # 12: Blue
    (0xFF, 0x00, 0xFF),  # 13: Magenta
    (0x00, 0xFF, 0xFF),  # 14: Cyan
    (0xFF, 0xFF, 0xFF),  # 15: White
]

# DiskObject fixed header length used by Deark
DISKOBJECT_LEN = 78

# Offsets (absolute) in DiskObject, matching the Deark scan
OFF_VERSION = 2

# Embedded Gadget starts at offset 4, length 44
OFF_GADGET = 4
GADGET_LEN = 44

# canvas width/height (Deark reads at absolute offsets 12/14)
OFF_MAIN_CANVAS_W = 12
OFF_MAIN_CANVAS_H = 14

# Deark reads SelectRender pointer at absolute offset 26 (used to infer 1 vs 2 icons)
OFF_SELECTRENDER_PTR = 26

# Deark reads icon revision at absolute offset 44 (low byte)
OFF_ICON_REVISION = 44

# icon type byte at 48
OFF_ICON_TYPE = 48

# presence fields (Deark uses nonzero to decide segment exists)
OFF_DEFAULTTOOL_PRESENCE = 50
OFF_TOOLTYPES_PRESENCE = 54
OFF_DRAWERDATA_PRESENCE = 66
OFF_TOOLWINDOW_PRESENCE = 70

# DiskObject icon position fields (LONG). This is what Workbench uses for placement.
OFF_CURRENTX = 58  # 0x3A
OFF_CURRENTY = 62  # 0x3E

# DrawerData segment size in Deark
DRAWERDATA_LEN = 56
# DrawerData begins with embedded NewWindow; Width/Height are the 3rd/4th WORDs
DD_NEWWIN_WIDTH_OFF = 4
DD_NEWWIN_HEIGHT_OFF = 6

# DrawerData2 length for revision==1 (Deark)
DRAWERDATA2_LEN = 6

# Structure field definitions for verbose dump and editing
# Format: (offset, size, signed, name, formatter)
# Sizes: 1=byte, 2=word, 4=long

@dataclass
class FieldDef:
    offset: int
    size: int
    signed: bool
    name: str
    fmt: Optional[Callable[[int], str]] = None

def _fmt_hex(v: int) -> str:
    return f"0x{v:X}"

def _fmt_icon_type(v: int) -> str:
    names = {1: "WBDISK", 2: "WBDRAWER", 3: "WBTOOL", 4: "WBPROJECT",
             5: "WBGARBAGE", 6: "WBDEVICE", 7: "WBKICK", 8: "WBAPPICON"}
    return f"{v} ({names.get(v, '?')})"

def _fmt_wb_version(v: int) -> str:
    # UserData low byte is the "revision" field
    # 0 = OS1.x format (no dd_Flags/dd_ViewModes)
    # 1 = OS2.x/v36+ format (has dd_Flags/dd_ViewModes after ToolWindow)
    rev = v & 0xFF
    if rev == 0:
        return f"0x{v:X} (OS1.x, no DrawerData2)"
    else:
        return f"0x{v:X} (OS2.x/v36+, has DrawerData2)"

def _fmt_position(v: int) -> str:
    if v == 0x80000000:
        return f"0x{v:X} (NO_ICON_POSITION)"
    return str(v)

def _fmt_magic(v: int) -> str:
    valid = "valid" if v == WB_DISKMAGIC else "INVALID"
    return f"0x{v:X} ({valid})"

# Gadget structure (embedded in DiskObject at offset 4)
GADGET_FIELDS = [
    FieldDef(0,  4, False, "NextGadget", _fmt_hex),
    FieldDef(4,  2, False, "LeftEdge"),
    FieldDef(6,  2, False, "TopEdge"),
    FieldDef(8,  2, False, "Width"),
    FieldDef(10, 2, False, "Height"),
    FieldDef(12, 2, False, "Flags", _fmt_hex),
    FieldDef(14, 2, False, "Activation", _fmt_hex),
    FieldDef(16, 2, False, "GadgetType"),
    FieldDef(18, 4, False, "GadgetRender", _fmt_hex),
    FieldDef(22, 4, False, "SelectRender", _fmt_hex),
    FieldDef(26, 4, False, "GadgetText", _fmt_hex),
    FieldDef(30, 4, False, "MutualExclude", _fmt_hex),
    FieldDef(34, 4, False, "SpecialInfo", _fmt_hex),
    FieldDef(38, 2, False, "GadgetID"),
    FieldDef(40, 4, False, "UserData", _fmt_wb_version),
]

# DiskObject structure (78 bytes header)
DISKOBJECT_FIELDS = [
    FieldDef(0,  2, False, "Magic", _fmt_magic),
    FieldDef(2,  2, False, "Version"),
    # Gadget is at offset 4, 44 bytes - handled separately
    FieldDef(48, 1, False, "Type", _fmt_icon_type),
    FieldDef(49, 1, False, "Padding"),
    FieldDef(50, 4, False, "DefaultTool", _fmt_hex),
    FieldDef(54, 4, False, "ToolTypes", _fmt_hex),
    FieldDef(58, 4, True,  "CurrentX", _fmt_position),
    FieldDef(62, 4, True,  "CurrentY", _fmt_position),
    FieldDef(66, 4, False, "DrawerData", _fmt_hex),
    FieldDef(70, 4, False, "ToolWindow", _fmt_hex),
    FieldDef(74, 4, False, "StackSize"),
]

# Image structure (20 bytes header per icon)
IMAGE_FIELDS = [
    FieldDef(0,  2, False, "LeftEdge"),
    FieldDef(2,  2, False, "TopEdge"),
    FieldDef(4,  2, False, "Width"),
    FieldDef(6,  2, False, "Height"),
    FieldDef(8,  2, False, "Depth"),
    FieldDef(10, 4, False, "ImageData", _fmt_hex),
    FieldDef(14, 1, True,  "PlanePick"),
    FieldDef(15, 1, True,  "PlaneOnOff"),
    FieldDef(16, 4, False, "NextImage", _fmt_hex),
]

# NewWindow structure (embedded in DrawerData, 48 bytes)
NEWWINDOW_FIELDS = [
    FieldDef(0,  2, True,  "LeftEdge"),
    FieldDef(2,  2, True,  "TopEdge"),
    FieldDef(4,  2, True,  "Width"),
    FieldDef(6,  2, True,  "Height"),
    FieldDef(8,  1, False, "DetailPen"),
    FieldDef(9,  1, False, "BlockPen"),
    FieldDef(10, 4, False, "IDCMPFlags", _fmt_hex),
    FieldDef(14, 4, False, "Flags", _fmt_hex),
    FieldDef(18, 4, False, "FirstGadget", _fmt_hex),
    FieldDef(22, 4, False, "CheckMark", _fmt_hex),
    FieldDef(26, 4, False, "Title", _fmt_hex),
    FieldDef(30, 4, False, "Screen", _fmt_hex),
    FieldDef(34, 4, False, "BitMap", _fmt_hex),
    FieldDef(38, 2, True,  "MinWidth"),
    FieldDef(40, 2, True,  "MinHeight"),
    FieldDef(42, 2, False, "MaxWidth"),
    FieldDef(44, 2, False, "MaxHeight"),
    FieldDef(46, 2, False, "Type"),
]

# DrawerData structure (56 bytes: NewWindow + 2 longs)
DRAWERDATA_FIELDS = [
    # NewWindow at offset 0 handled separately
    FieldDef(48, 4, True, "CurrentX"),
    FieldDef(52, 4, True, "CurrentY"),
]

# DrawerData2 for OS 2.x (6 bytes after tooltypes)
DRAWERDATA2_FIELDS = [
    FieldDef(0, 4, False, "Flags", _fmt_hex),
    FieldDef(4, 2, False, "ViewModes"),
]

# ToolTypes table encoding per Deark:
# u32 num_entries_raw; num_entries = num_entries_raw/4 - 1
# then for each entry: u32 tlen, then tlen bytes data
MAX_TOOLTYPES = 1000
MAX_TLEN = 10000

_tt_paren_re = re.compile(r"^\((.*)\)$")

def be_u16(b: bytes, off: int) -> int:
    return struct.unpack_from(">H", b, off)[0]

def be_u32(b: bytes, off: int) -> int:
    return struct.unpack_from(">I", b, off)[0]

def be_i32(b: bytes, off: int) -> int:
    return struct.unpack_from(">i", b, off)[0]

def put_be_i32(buf: bytearray, off: int, v: int) -> None:
    struct.pack_into(">i", buf, off, int(v))

def put_be_u16(buf: bytearray, off: int, v: int) -> None:
    if not (0 <= v <= 0xFFFF):
        raise ValueError("UWORD out of range")
    struct.pack_into(">H", buf, off, int(v))

def u32_at(buf: bytes, pos: int, strict: bool) -> Tuple[int, int]:
    if pos + 4 > len(buf):
        if strict:
            raise ValueError("Out of range reading u32")
        return 0, pos
    return be_u32(buf, pos), pos + 4

def is_diskobject(buf: bytes) -> bool:
    return len(buf) >= 4 and be_u16(buf, 0) == WB_DISKMAGIC

def icon_type_name(t: int) -> str:
    return {
        1: "disk",
        2: "drawer",
        3: "tool",
        4: "project",
        6: "device",
        7: "kick",
    }.get(t, "?")

def bytes_to_tt_str(raw: bytes) -> str:
    # ToolTypes often include a trailing NUL; strip NULs for display/logic.
    s = raw.rstrip(b"\0")
    return s.decode("latin-1", errors="replace")

def tt_str_to_bytes(s: str, keep_nul: bool) -> bytes:
    b = s.encode("latin-1", errors="strict")
    return b + (b"\0" if keep_nul else b"")

def split_kv(s: str) -> Tuple[str, Optional[str]]:
    if "=" not in s:
        return (s, None)
    k, v = s.split("=", 1)
    return k, v

def key_eq(a: str, b: str, ignore_case: bool) -> bool:
    return a.lower() == b.lower() if ignore_case else a == b

def canon_key(user_key: str) -> str:
    s = user_key.strip()
    m = _tt_paren_re.match(s)
    if m:
        return m.group(1).strip()
    return s

@dataclass
class TTItem:
    raw: str              # normalized display string (no trailing NUL)
    key: str              # canonical key (no parens)
    kind: str             # "kv" | "bool"
    value: Optional[str]  # for kv: string; for bool: "true"/"false"
    negated: bool         # True if (KEY)

def parse_tt_item(line: str) -> TTItem:
    s = line.strip()
    m = _tt_paren_re.match(s)
    if m:
        k = m.group(1).strip()
        return TTItem(raw=s, key=k, kind="bool", value="false", negated=True)
    if "=" in s:
        k, v = s.split("=", 1)
        return TTItem(raw=s, key=k.strip(), kind="kv", value=v, negated=False)
    # boolean true
    return TTItem(raw=s, key=s, kind="bool", value="true", negated=False

    )

@dataclass
class ParsedIcon:
    data: bytearray
    version: int
    revision: int
    icon_type: int
    has_drawerdata: bool
    has_defaulttool: bool
    has_tooltypes: bool
    has_toolwindow: bool
    num_main_icons: int

    drawerdata: Optional[bytes]
    main_icons_blob: bytes
    defaulttool: Optional[bytes]
    tooltypes_raw_entries: List[bytes]
    toolwindow: Optional[bytes]
    drawerdata2: Optional[bytes]
    glowicons: Optional[bytes]

    tooltypes_pos: Optional[int]

def get_main_icon_size(buf: bytes, pos: int, strict: bool) -> int:
    if pos + 20 > len(buf):
        if strict:
            raise ValueError("Main icon header out of range")
        return 0
    width = be_u16(buf, pos + 4)
    height = be_u16(buf, pos + 6)
    depth = be_u16(buf, pos + 8)
    src_rowspan = ((width + 15) // 16) * 2
    src_planespan = src_rowspan * height
    bytesused = 20 + src_planespan * depth
    if strict:
        if depth < 1 or depth > 8:
            raise ValueError(f"Unsupported depth {depth}")
        if bytesused <= 20 or bytesused > 10_000_000:
            raise ValueError("Main icon size unreasonable")
        if pos + bytesused > len(buf):
            raise ValueError("Main icon bitmap out of range")
    return int(bytesused)

def parse_tooltypes_table(buf: bytes, pos: int, strict: bool) -> Tuple[List[bytes], int]:
    pos0 = pos
    num_entries_raw, pos = u32_at(buf, pos, strict=strict)
    if num_entries_raw == 0:
        return [], pos - pos0
    if strict and (num_entries_raw % 4 != 0):
        raise ValueError("ToolTypes header not multiple of 4")
    num_entries = (num_entries_raw // 4) - 1
    if strict:
        if num_entries < 0 or num_entries > MAX_TOOLTYPES:
            raise ValueError(f"ToolTypes count unreasonable: {num_entries}")
    entries: List[bytes] = []
    for _ in range(max(0, num_entries)):
        tlen, pos = u32_at(buf, pos, strict=strict)
        if strict and tlen > MAX_TLEN:
            raise ValueError("ToolType entry too large")
        if pos + tlen > len(buf):
            raise ValueError("ToolType entry out of range")
        entries.append(bytes(buf[pos:pos + tlen]))
        pos += tlen
    return entries, pos - pos0

def build_tooltypes_table(entries: List[bytes]) -> bytes:
    num_entries_raw = 4 * (len(entries) + 1)
    out = bytearray()
    out += struct.pack(">I", num_entries_raw)
    for e in entries:
        out += struct.pack(">I", len(e))
        out += e
    return bytes(out)

def find_glowicons_form(buf: bytes, start_pos: int) -> int:
    """
    Search for FORM ICON chunk starting from start_pos.
    Returns the position of "FORM" or -1 if not found.

    This properly handles "FORM" appearing in ToolTypes (e.g., "FORMAT=0")
    by verifying the chunk is actually "FORM....ICON".
    """
    pos = start_pos
    while True:
        # Search for "FORM"
        form_pos = buf.find(b"FORM", pos)
        if form_pos == -1:
            return -1

        # Check if we have enough data for the header
        if len(buf) < form_pos + 12:
            return -1

        # Verify this is FORM ICON (not just "FORMAT" or other text)
        form_type = buf[form_pos + 8:form_pos + 12]
        if form_type == b"ICON":
            return form_pos

        # Not ICON, keep searching after this position
        pos = form_pos + 1

    return -1


def detect_glowicons_tail(buf: bytes, pos: int) -> Optional[bytes]:
    """
    Detect GlowIcons FORM ICON data after traditional icon data.
    Returns the FORM ICON chunk (and any trailing data) or remaining bytes.
    """
    if pos < 0 or pos >= len(buf):
        return None

    # Search for FORM ICON starting from pos
    form_pos = find_glowicons_form(buf, pos)
    if form_pos >= pos:
        return bytes(buf[form_pos:])

    # No FORM ICON found, but there might be other trailing data
    rem = len(buf) - pos
    if rem > 0:
        return bytes(buf[pos:])
    return None


# --- GlowIcons parsing ---

def unpack_rle_8bit(data: bytes, expected_size: int) -> bytes:
    """
    Decompress 8-bit RLE data (icon.library format for colormap).
    Similar to PackBits:
    - n < 128: copy n+1 literal bytes
    - n >= 128: repeat next byte (256-n)+1 times
    """
    result = bytearray()
    i = 0

    while i < len(data) and len(result) < expected_size:
        if i + 1 > len(data):
            break
        n = data[i]
        i += 1

        if n < 128:
            # Literal run: copy n+1 bytes
            count = n + 1
            result.extend(data[i:i + count])
            i += count
        else:
            # Replicate run: repeat next byte (256-n)+1 times
            if i < len(data):
                count = (256 - n) + 1
                result.extend([data[i]] * count)
                i += 1

    return bytes(result[:expected_size])


def unpack_rle_bitpacked(data: bytes, expected_pixels: int, depth: int) -> bytes:
    """
    Decompress bit-packed RLE data (icon.library format for image).
    Control bytes are 8 bits, data values are 'depth' bits each.
    Based on icon.library decompressdata routine.
    """
    if depth == 8:
        return unpack_rle_8bit(data, expected_pixels)

    result = bytearray()

    # Bit buffer for reading from the packed stream
    bit_buffer = 0
    bits_in_buffer = 0
    data_pos = 0

    def read_bits(num_bits: int) -> int:
        nonlocal bit_buffer, bits_in_buffer, data_pos

        while bits_in_buffer < num_bits:
            if data_pos >= len(data):
                return -1
            byte = data[data_pos]
            data_pos += 1
            bit_buffer = (bit_buffer << 8) | byte
            bits_in_buffer += 8

        bits_in_buffer -= num_bits
        value = (bit_buffer >> bits_in_buffer) & ((1 << num_bits) - 1)
        return value

    while len(result) < expected_pixels and data_pos < len(data):
        # Read 8-bit control byte
        control = read_bits(8)
        if control < 0:
            break

        # Sign-extend the control byte
        if control >= 128:
            control = control - 256

        if control >= 0:
            # Literal run: copy (control + 1) pixel values
            count = control + 1
            for _ in range(count):
                if len(result) >= expected_pixels:
                    break
                pixel = read_bits(depth)
                if pixel < 0:
                    break
                result.append(pixel)
        else:
            # Repeat run: repeat next pixel value (-control + 1) times
            count = -control + 1
            pixel = read_bits(depth)
            if pixel < 0:
                break
            for _ in range(count):
                if len(result) >= expected_pixels:
                    break
                result.append(pixel)

    return bytes(result)


def parse_glowicons(data: bytes) -> Optional[Dict]:
    """
    Parse GlowIcons FORM ICON data.
    Returns dict with 'width', 'height', 'rgba', 'has_select', 'select_rgba' or None.
    """
    if len(data) < 12 or data[0:4] != b"FORM" or data[8:12] != b"ICON":
        return None

    form_size = struct.unpack(">I", data[4:8])[0]
    pos = 12  # Skip "FORM" + size + "ICON"

    face_info = None
    images = []

    while pos < min(len(data), form_size + 8):
        if pos + 8 > len(data):
            break

        chunk_id = data[pos:pos + 4]
        chunk_size = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        chunk_data = data[pos + 8:pos + 8 + chunk_size]

        if chunk_id == b"FACE":
            # FACE chunk: width-1, height-1, flags, aspect
            if len(chunk_data) >= 4:
                face_info = {
                    "width": chunk_data[0] + 1,
                    "height": chunk_data[1] + 1,
                    "flags": chunk_data[2],
                    "aspect": chunk_data[3],
                }
        elif chunk_id == b"IMAG":
            img = parse_imag_chunk(chunk_data, face_info)
            if img:
                images.append(img)
        elif chunk_id == b"ARGB":
            img = parse_argb_chunk(chunk_data)
            if img:
                images.append(img)

        # Move to next chunk (aligned to word boundary)
        pos += 8 + chunk_size
        if chunk_size % 2:
            pos += 1

    if not images:
        return None

    result = {
        "width": images[0]["width"],
        "height": images[0]["height"],
        "rgba": images[0]["rgba"],
        "has_select": len(images) > 1,
    }
    if len(images) > 1:
        result["select_rgba"] = images[1]["rgba"]
        result["select_width"] = images[1]["width"]
        result["select_height"] = images[1]["height"]

    return result


def parse_imag_chunk(data: bytes, face_info: Optional[Dict]) -> Optional[Dict]:
    """
    Parse IMAG chunk (palette-mapped compressed image).

    IMAG header (10 bytes):
      $00 byte transparent color number
      $01 byte number of colors - 1
      $02 byte flags (bit0=transparency)
      $03 byte compressed image flag
      $04 byte compressed colormap flag
      $05 byte depth (bits per pixel)
      $06 word compressed image size - 1
      $08 word compressed colormap size - 1

    Data order: IMAGE data first, then COLORMAP data.
    """
    if len(data) < 10 or not face_info:
        return None

    width = face_info["width"]
    height = face_info["height"]

    transparent_color = data[0]
    num_colors = data[1] + 1
    flags = data[2]
    image_compressed = data[3] != 0
    colormap_compressed = data[4] != 0
    depth = data[5]
    image_size = struct.unpack(">H", data[6:8])[0] + 1
    colormap_size = struct.unpack(">H", data[8:10])[0] + 1

    has_transparency = (flags & 1) != 0

    pos = 10  # After header
    expected_pixels = width * height

    # Data order: IMAGE first, then COLORMAP
    # Read image data
    if image_size > 1 and pos + image_size <= len(data):
        raw_image_data = data[pos:pos + image_size]
        pos += image_size
    else:
        raw_image_data = data[pos:]
        pos = len(data)

    # Read colormap data
    palette = None
    if colormap_size > 1 and pos + colormap_size <= len(data):
        raw_colormap_data = data[pos:pos + colormap_size]

        # Decompress colormap (8-bit RLE)
        if colormap_compressed:
            colormap_data = unpack_rle_8bit(raw_colormap_data, num_colors * 3)
        else:
            colormap_data = raw_colormap_data

        # Parse RGB palette
        palette = []
        for i in range(0, min(len(colormap_data), num_colors * 3), 3):
            if i + 2 < len(colormap_data):
                palette.append((colormap_data[i], colormap_data[i + 1], colormap_data[i + 2]))

    # Decompress image data
    if image_compressed:
        image_data = unpack_rle_bitpacked(raw_image_data, expected_pixels, depth)
    else:
        image_data = raw_image_data

    if len(image_data) < expected_pixels:
        return None

    # Use default palette if none provided
    if palette is None or len(palette) == 0:
        if num_colors <= 4:
            palette = WB13_COLORS[:4]
        elif num_colors <= 8:
            palette = WB20_COLORS
        else:
            palette = PALETTE_16

    # Convert indexed to RGBA
    rgba = bytearray(width * height * 4)
    for i in range(width * height):
        idx = image_data[i] if i < len(image_data) else 0
        if idx < len(palette):
            r, g, b = palette[idx]
        else:
            r, g, b = 0, 0, 0

        if has_transparency and idx == transparent_color:
            a = 0
        else:
            a = 255

        rgba[i * 4] = r
        rgba[i * 4 + 1] = g
        rgba[i * 4 + 2] = b
        rgba[i * 4 + 3] = a

    return {"width": width, "height": height, "rgba": bytes(rgba)}


def parse_argb_chunk(data: bytes) -> Optional[Dict]:
    """Parse ARGB chunk (OS4 true-color format)."""
    if len(data) < 4:
        return None

    width = struct.unpack(">H", data[0:2])[0]
    height = struct.unpack(">H", data[2:4])[0]

    if width == 0 or height == 0:
        return None

    expected_size = width * height * 4
    pixel_data = data[4:]

    if len(pixel_data) < expected_size:
        return None

    # ARGB to RGBA conversion
    rgba = bytearray(expected_size)
    for i in range(width * height):
        offset = i * 4
        a = pixel_data[offset]
        r = pixel_data[offset + 1]
        g = pixel_data[offset + 2]
        b = pixel_data[offset + 3]
        rgba[offset] = r
        rgba[offset + 1] = g
        rgba[offset + 2] = b
        rgba[offset + 3] = a

    return {"width": width, "height": height, "rgba": bytes(rgba)}

def parse_icon_file(path: str, strict: bool) -> ParsedIcon:
    data = bytearray(open(path, "rb").read())
    if not is_diskobject(data):
        raise ValueError("Not an Amiga icon (.info) (WB_DISKMAGIC mismatch)")
    if strict and len(data) < DISKOBJECT_LEN:
        raise ValueError("File too small for DiskObject")

    version = be_u16(data, OFF_VERSION)
    revision = be_u32(data, OFF_ICON_REVISION) & 0xFF
    itype = data[OFF_ICON_TYPE]

    has_defaulttool = (be_u32(data, OFF_DEFAULTTOOL_PRESENCE) != 0)
    has_tooltypes = (be_u32(data, OFF_TOOLTYPES_PRESENCE) != 0)
    has_drawerdata = (be_u32(data, OFF_DRAWERDATA_PRESENCE) != 0)
    has_toolwindow = (be_u32(data, OFF_TOOLWINDOW_PRESENCE) != 0)

    selectrender_ptr = be_u32(data, OFF_SELECTRENDER_PTR)
    num_main_icons = 1 if selectrender_ptr == 0 else 2

    pos = DISKOBJECT_LEN

    drawerdata = None
    if has_drawerdata:
        if strict and pos + DRAWERDATA_LEN > len(data):
            raise ValueError("DrawerData out of range")
        drawerdata = bytes(data[pos:pos + DRAWERDATA_LEN])
        pos += DRAWERDATA_LEN

    main_start = pos
    for _ in range(num_main_icons):
        sz = get_main_icon_size(data, pos, strict=strict)
        pos += sz
    if strict and pos > len(data):
        raise ValueError("Main icons overrun file")
    main_icons_blob = bytes(data[main_start:pos])

    defaulttool = None
    if has_defaulttool:
        if strict and pos + 4 > len(data):
            raise ValueError("DefaultTool header out of range")
        dlen = be_u32(data, pos)
        pos += 4
        if strict and pos + dlen > len(data):
            raise ValueError("DefaultTool data out of range")
        defaulttool = bytes(data[pos-4:pos + dlen])  # include length field
        pos += dlen

    tooltypes_pos = None
    tooltypes_entries: List[bytes] = []
    if has_tooltypes:
        tooltypes_pos = pos
        entries, used = parse_tooltypes_table(data, pos, strict=strict)
        tooltypes_entries = entries
        pos += used

    toolwindow = None
    if has_toolwindow:
        if strict and pos + 4 > len(data):
            raise ValueError("ToolWindow header out of range")
        wlen = be_u32(data, pos)
        if strict and pos + 4 + wlen > len(data):
            raise ValueError("ToolWindow data out of range")
        toolwindow = bytes(data[pos:pos + 4 + wlen])
        pos += 4 + wlen

    drawerdata2 = None
    if has_drawerdata and revision == 1:
        if pos + DRAWERDATA2_LEN > len(data):
            if strict:
                raise ValueError("DrawerData2 out of range")
            # Non-strict: only read if we have at least some data
            # (icon.library handles truncated files gracefully)
            remaining = len(data) - pos
            if remaining > 0:
                # Pad with zeros if truncated
                drawerdata2 = bytes(data[pos:pos + DRAWERDATA2_LEN])
                if len(drawerdata2) < DRAWERDATA2_LEN:
                    drawerdata2 = drawerdata2 + bytes(DRAWERDATA2_LEN - len(drawerdata2))
                pos = len(data)  # We've consumed everything
        else:
            drawerdata2 = bytes(data[pos:pos + DRAWERDATA2_LEN])
            pos += DRAWERDATA2_LEN

    glowicons = detect_glowicons_tail(data, pos)

    return ParsedIcon(
        data=data,
        version=version,
        revision=revision,
        icon_type=itype,
        has_drawerdata=has_drawerdata,
        has_defaulttool=has_defaulttool,
        has_tooltypes=has_tooltypes,
        has_toolwindow=has_toolwindow,
        num_main_icons=num_main_icons,
        drawerdata=drawerdata,
        main_icons_blob=main_icons_blob,
        defaulttool=defaulttool,
        tooltypes_raw_entries=tooltypes_entries,
        toolwindow=toolwindow,
        drawerdata2=drawerdata2,
        glowicons=glowicons,
        tooltypes_pos=tooltypes_pos,
    )

def set_current_xy(icon: ParsedIcon, x: int, y: int) -> None:
    if len(icon.data) >= OFF_CURRENTY + 4:
        put_be_i32(icon.data, OFF_CURRENTX, x)
        put_be_i32(icon.data, OFF_CURRENTY, y)
    else:
        raise ValueError("Icon too small to have CurrentX/CurrentY")

def set_drawer_winsize(icon: ParsedIcon, w: int, h: int) -> bool:
    if not icon.has_drawerdata or icon.drawerdata is None:
        return False
    dd = bytearray(icon.drawerdata)
    put_be_u16(dd, DD_NEWWIN_WIDTH_OFF, w)
    put_be_u16(dd, DD_NEWWIN_HEIGHT_OFF, h)
    icon.drawerdata = bytes(dd)
    return True

def apply_tooltypes_ops(
    entries_raw: List[bytes],
    op_set_kv: Optional[Tuple[str, str]],
    op_set_flag: Optional[str],
    op_unset_flag: Optional[str],
    op_del: Optional[str],
    op_norm: bool,
    ignore_case: bool
) -> List[bytes]:
    entries = [bytes_to_tt_str(e) for e in entries_raw]

    def matches_key(line: str, want_key: str) -> bool:
        item = parse_tt_item(line)
        return key_eq(item.key, want_key, ignore_case)

    # delete (removes KEY, (KEY), and KEY=VAL)
    if op_del:
        want = canon_key(op_del)
        entries = [s for s in entries if not matches_key(s, want)]

    # set KV (removes all prior forms, then writes KEY=VAL)
    if op_set_kv:
        k, v = op_set_kv
        want = canon_key(k)
        entries = [s for s in entries if not matches_key(s, want)]
        entries.append(f"{want}={v}")

    # set flag true (removes all prior forms, then writes KEY)
    if op_set_flag:
        want = canon_key(op_set_flag)
        entries = [s for s in entries if not matches_key(s, want)]
        entries.append(f"{want}")

    # unset flag (removes all prior forms, then writes (KEY))
    if op_unset_flag:
        want = canon_key(op_unset_flag)
        entries = [s for s in entries if not matches_key(s, want)]
        entries.append(f"({want})")

    if op_norm:
        # last-wins across all forms (kv, KEY, (KEY))
        last_by_key: dict[str, str] = {}
        other: List[str] = []

        def canon(k: str) -> str:
            return k.lower() if ignore_case else k

        for s in entries:
            s2 = s.strip()
            if s2 == "":
                continue
            item = parse_tt_item(s2)
            if item.key == "":
                continue
            last_by_key[canon(item.key)] = s2

        # Preserve stable order by original appearance of first-seen key
        seen = set()
        for s in entries:
            item = parse_tt_item(s)
            ck = canon(item.key)
            if ck in seen:
                continue
            if ck in last_by_key:
                other.append(last_by_key[ck])
                seen.add(ck)

        entries = other

    # Re-encode. Preserve original trailing NUL per entry position if possible;
    # otherwise default to keeping NUL (it’s common and harmless).
    new_raw: List[bytes] = []
    for i, s in enumerate(entries):
        keep_nul = True
        if i < len(entries_raw):
            keep_nul = entries_raw[i].endswith(b"\0")
        new_raw.append(tt_str_to_bytes(s, keep_nul=keep_nul))
    return new_raw

def rebuild_file(icon: ParsedIcon, new_tooltypes: Optional[List[bytes]], compact: bool) -> bytes:
    out = bytearray()

    # DiskObject header (78 bytes) with any in-place edits already applied
    out += icon.data[:DISKOBJECT_LEN]

    # DrawerData
    if icon.has_drawerdata:
        if icon.drawerdata is None:
            raise ValueError("DrawerData flagged but missing")
        out += icon.drawerdata

    # Main icons blob
    out += icon.main_icons_blob

    # DefaultTool segment
    if icon.has_defaulttool:
        if icon.defaulttool is None:
            raise ValueError("DefaultTool flagged but missing")
        out += icon.defaulttool

    # ToolTypes
    if icon.has_tooltypes:
        if new_tooltypes is None and not compact:
            if icon.tooltypes_pos is None:
                raise ValueError("ToolTypes flagged but position unknown")
            entries, used = parse_tooltypes_table(icon.data, icon.tooltypes_pos, strict=False)
            out += icon.data[icon.tooltypes_pos:icon.tooltypes_pos + used]
        else:
            tt_entries = new_tooltypes if new_tooltypes is not None else icon.tooltypes_raw_entries
            out += build_tooltypes_table(tt_entries)

    # ToolWindow
    if icon.has_toolwindow:
        if icon.toolwindow is None:
            raise ValueError("ToolWindow flagged but missing")
        out += icon.toolwindow

    # DrawerData2 (dd_Flags + dd_ViewModes, 6 bytes)
    # Write if: drawerdata2 exists OR (has_drawerdata AND revision >= 1)
    # Per icon.library: dd_Flags/dd_ViewModes are written after ToolWindow if DrawerData present
    if icon.drawerdata2 is not None:
        # Ensure we write exactly 6 bytes
        dd2 = icon.drawerdata2
        if len(dd2) < DRAWERDATA2_LEN:
            dd2 = dd2 + bytes(DRAWERDATA2_LEN - len(dd2))
        out += dd2[:DRAWERDATA2_LEN]
    elif icon.has_drawerdata and icon.revision >= 1:
        # Revision 1+ expects dd_Flags/dd_ViewModes but we don't have them - write zeros
        out += bytes(DRAWERDATA2_LEN)

    # GlowIcons / extra tail
    if icon.glowicons:
        out += icon.glowicons

    return bytes(out)


# --- Field access helpers for verbose dump and editing ---

def read_field(buf: bytes, field: FieldDef) -> int:
    """Read a field value from buffer at the field's offset."""
    off = field.offset
    if field.size == 1:
        val = buf[off]
        if field.signed and val >= 0x80:
            val -= 0x100
    elif field.size == 2:
        val = be_u16(buf, off)
        if field.signed and val >= 0x8000:
            val -= 0x10000
    elif field.size == 4:
        val = be_u32(buf, off)
        if field.signed and val >= 0x80000000:
            val -= 0x100000000
    else:
        raise ValueError(f"Unsupported field size: {field.size}")
    return val


def write_field(buf: bytearray, offset: int, size: int, signed: bool, value: int) -> None:
    """Write a field value to buffer at the given offset."""
    # Convert signed to unsigned for packing
    if signed and value < 0:
        if size == 1:
            value += 0x100
        elif size == 2:
            value += 0x10000
        elif size == 4:
            value += 0x100000000

    if size == 1:
        buf[offset] = value & 0xFF
    elif size == 2:
        buf[offset] = (value >> 8) & 0xFF
        buf[offset + 1] = value & 0xFF
    elif size == 4:
        buf[offset] = (value >> 24) & 0xFF
        buf[offset + 1] = (value >> 16) & 0xFF
        buf[offset + 2] = (value >> 8) & 0xFF
        buf[offset + 3] = value & 0xFF


def format_field(field: FieldDef, value: int) -> str:
    """Format a field value for display."""
    if field.fmt:
        return field.fmt(value)
    return str(value)


def dump_fields(prefix: str, buf: bytes, fields: List[FieldDef]) -> None:
    """Print all fields in a structure with path notation."""
    for f in fields:
        if f.offset + f.size > len(buf):
            continue
        val = read_field(buf, f)
        print(f"{prefix}:{f.name}={format_field(f, val)}")


def dump_icon_verbose(icon: ParsedIcon) -> None:
    """Print full structure dump of an icon file."""
    # DiskObject header fields
    for f in DISKOBJECT_FIELDS:
        if f.offset + f.size <= len(icon.data):
            val = read_field(icon.data, f)
            print(f"DiskObject:{f.name}={format_field(f, val)}")

    # Embedded Gadget (at offset 4)
    gadget_buf = icon.data[OFF_GADGET:OFF_GADGET + GADGET_LEN]
    dump_fields("DiskObject:Gadget", gadget_buf, GADGET_FIELDS)

    # DrawerData if present
    if icon.has_drawerdata and icon.drawerdata:
        # NewWindow is embedded at start of DrawerData
        dump_fields("DrawerData:NewWindow", icon.drawerdata, NEWWINDOW_FIELDS)
        dump_fields("DrawerData", icon.drawerdata, DRAWERDATA_FIELDS)

    # Main icon image headers
    if icon.main_icons_blob:
        pos = 0
        for i in range(icon.num_main_icons):
            name = "Icon" if i == 0 else "IconSelect"
            if pos + 20 <= len(icon.main_icons_blob):
                dump_fields(name, icon.main_icons_blob[pos:], IMAGE_FIELDS)
                sz = get_main_icon_size(icon.main_icons_blob, pos, strict=False)
                pos += sz

    # DefaultTool
    if icon.has_defaulttool and icon.defaulttool:
        dlen = be_u32(icon.defaulttool, 0)
        dtool = icon.defaulttool[4:4+dlen].rstrip(b'\0').decode('latin-1', errors='replace')
        print(f'DefaultTool="{dtool}"')

    # ToolTypes
    if icon.has_tooltypes and icon.tooltypes_raw_entries:
        for idx, entry in enumerate(icon.tooltypes_raw_entries):
            print(f'ToolTypes[{idx}]="{bytes_to_tt_str(entry)}"')

    # DrawerData2 for OS 2.x (dd_Flags + dd_ViewModes)
    if icon.drawerdata2:
        dump_fields("DrawerData2", icon.drawerdata2, DRAWERDATA2_FIELDS)
    elif icon.has_drawerdata and icon.revision >= 1:
        # Expected but not present in file
        print("DrawerData2: (expected but not found in file)")


# --- Structured editing ---

def find_field_by_path(path: str) -> Tuple[Optional[FieldDef], str, int]:
    """
    Parse a path like "DiskObject:Gadget:LeftEdge" and return (field, structure_name, base_offset).
    Returns (None, "", 0) if not found.
    """
    parts = path.split(":")
    if len(parts) < 2:
        return None, "", 0

    # Handle nested paths
    if parts[0] == "DiskObject":
        if len(parts) == 2:
            # Direct DiskObject field
            for f in DISKOBJECT_FIELDS:
                if f.name == parts[1]:
                    return f, "DiskObject", 0
            return None, "", 0
        elif len(parts) == 3 and parts[1] == "Gadget":
            # DiskObject:Gadget:Field
            for f in GADGET_FIELDS:
                if f.name == parts[2]:
                    return f, "Gadget", OFF_GADGET
            return None, "", 0

    elif parts[0] == "DrawerData":
        if len(parts) == 2:
            for f in DRAWERDATA_FIELDS:
                if f.name == parts[1]:
                    return f, "DrawerData", 0
            return None, "", 0
        elif len(parts) == 3 and parts[1] == "NewWindow":
            for f in NEWWINDOW_FIELDS:
                if f.name == parts[2]:
                    return f, "NewWindow", 0
            return None, "", 0

    elif parts[0] == "DrawerData2":
        # DrawerData2:Flags or DrawerData2:ViewModes
        if len(parts) == 2:
            for f in DRAWERDATA2_FIELDS:
                if f.name == parts[1]:
                    return f, "DrawerData2", 0
            return None, "", 0

    elif parts[0] in ("Icon", "IconSelect"):
        if len(parts) == 2:
            for f in IMAGE_FIELDS:
                if f.name == parts[1]:
                    return f, parts[0], 0  # offset determined at runtime
            return None, "", 0

    return None, "", 0


def apply_edit(icon: ParsedIcon, edit_spec: str) -> bool:
    """
    Apply an edit specification like "DiskObject:Gadget:LeftEdge=100".
    Returns True on success, False on error.
    """
    if "=" not in edit_spec:
        print(f"Invalid edit spec (missing '='): {edit_spec}", file=sys.stderr)
        return False

    path, value_str = edit_spec.split("=", 1)
    path = path.strip()
    value_str = value_str.strip()

    # Parse value (hex or decimal)
    try:
        if value_str.lower().startswith("0x"):
            value = int(value_str, 16)
        else:
            value = int(value_str)
    except ValueError:
        print(f"Invalid value: {value_str}", file=sys.stderr)
        return False

    field, struct_name, base_offset = find_field_by_path(path)
    if field is None:
        print(f"Unknown field path: {path}", file=sys.stderr)
        return False

    # Determine which buffer to edit
    if struct_name in ("DiskObject", "Gadget"):
        # Edit in the main data buffer
        offset = base_offset + field.offset
        if offset + field.size > len(icon.data):
            print(f"Field offset out of range: {path}", file=sys.stderr)
            return False
        write_field(icon.data, offset, field.size, field.signed, value)
        return True

    elif struct_name == "DrawerData":
        if not icon.has_drawerdata or icon.drawerdata is None:
            print(f"No DrawerData in this icon", file=sys.stderr)
            return False
        dd = bytearray(icon.drawerdata)
        write_field(dd, field.offset, field.size, field.signed, value)
        icon.drawerdata = bytes(dd)
        return True

    elif struct_name == "NewWindow":
        if not icon.has_drawerdata or icon.drawerdata is None:
            print(f"No DrawerData/NewWindow in this icon", file=sys.stderr)
            return False
        dd = bytearray(icon.drawerdata)
        write_field(dd, field.offset, field.size, field.signed, value)
        icon.drawerdata = bytes(dd)
        return True

    elif struct_name == "DrawerData2":
        # Editing dd_Flags or dd_ViewModes
        if not icon.has_drawerdata:
            print(f"No DrawerData in this icon (required for DrawerData2)", file=sys.stderr)
            return False
        # Ensure we have a drawerdata2 buffer, creating one if needed
        if icon.drawerdata2 is None:
            # Create default DrawerData2 (dd_Flags=0, dd_ViewModes=0)
            icon.drawerdata2 = bytes(6)
        dd2 = bytearray(icon.drawerdata2)
        # Extend if needed
        while len(dd2) < DRAWERDATA2_LEN:
            dd2.append(0)
        write_field(dd2, field.offset, field.size, field.signed, value)
        icon.drawerdata2 = bytes(dd2)
        # Ensure revision is set to 1 (required for DrawerData2 to be recognized)
        if icon.revision != 1:
            icon.revision = 1
            # Update UserData low byte in DiskObject header
            icon.data[OFF_ICON_REVISION + 3] = 1
        return True

    elif struct_name in ("Icon", "IconSelect"):
        if not icon.main_icons_blob:
            print(f"No icon images in this file", file=sys.stderr)
            return False
        blob = bytearray(icon.main_icons_blob)
        # Find offset of the target icon
        offset = 0
        if struct_name == "IconSelect":
            if icon.num_main_icons < 2:
                print(f"No select icon in this file", file=sys.stderr)
                return False
            offset = get_main_icon_size(blob, 0, strict=False)
        write_field(blob, offset + field.offset, field.size, field.signed, value)
        icon.main_icons_blob = bytes(blob)
        return True

    return False


# --- PNG export/import ---

def find_edge_background(pixels: List[List[int]], width: int, height: int) -> List[List[bool]]:
    """Find color 0 pixels connected to the image edge using flood fill.

    Returns a 2D array of booleans - True for pixels that should be transparent
    (color 0 and connected to the edge), False otherwise.

    This properly handles icons with color 0 used both for transparent background
    AND as an interior color (e.g., gray in MagicWB icons).
    """
    from collections import deque

    # Result: True = this pixel should be transparent
    is_edge = [[False] * width for _ in range(height)]

    # Use a queue for flood fill from all edge pixels that are color 0
    queue = deque()

    # Add all edge pixels that are color 0 to the queue
    for x in range(width):
        # Top edge
        if pixels[0][x] == 0 and not is_edge[0][x]:
            is_edge[0][x] = True
            queue.append((x, 0))
        # Bottom edge
        if pixels[height - 1][x] == 0 and not is_edge[height - 1][x]:
            is_edge[height - 1][x] = True
            queue.append((x, height - 1))

    for y in range(height):
        # Left edge
        if pixels[y][0] == 0 and not is_edge[y][0]:
            is_edge[y][0] = True
            queue.append((0, y))
        # Right edge
        if pixels[y][width - 1] == 0 and not is_edge[y][width - 1]:
            is_edge[y][width - 1] = True
            queue.append((width - 1, y))

    # Flood fill to find all connected color 0 pixels
    while queue:
        x, y = queue.popleft()

        # Check 4 neighbors
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                if pixels[ny][nx] == 0 and not is_edge[ny][nx]:
                    is_edge[ny][nx] = True
                    queue.append((nx, ny))

    return is_edge


def get_icon_image_info(blob: bytes, icon_index: int) -> Tuple[int, int, int, int, int]:
    """
    Get icon image info: (offset, width, height, depth, data_size).
    icon_index: 0 for main icon, 1 for select icon.
    """
    pos = 0
    for i in range(icon_index):
        pos += get_main_icon_size(blob, pos, strict=False)

    if pos + 20 > len(blob):
        raise ValueError("Icon header out of range")

    width = be_u16(blob, pos + 4)
    height = be_u16(blob, pos + 6)
    depth = be_u16(blob, pos + 8)
    row_bytes = ((width + 15) // 16) * 2
    plane_size = row_bytes * height
    data_size = plane_size * depth

    return pos, width, height, depth, data_size


def decode_planar_to_chunky(blob: bytes, pos: int, width: int, height: int, depth: int) -> List[List[int]]:
    """
    Decode Amiga planar bitmap to chunky pixel array.
    Returns 2D array of pixel indices [y][x].
    """
    row_bytes = ((width + 15) // 16) * 2
    plane_size = row_bytes * height
    data_start = pos + 20  # After IMAGE header

    pixels = [[0] * width for _ in range(height)]

    for plane in range(depth):
        plane_offset = data_start + plane * plane_size
        for y in range(height):
            row_offset = plane_offset + y * row_bytes
            for x in range(width):
                byte_idx = row_offset + (x // 8)
                bit_idx = 7 - (x % 8)
                if byte_idx < len(blob):
                    if blob[byte_idx] & (1 << bit_idx):
                        pixels[y][x] |= (1 << plane)

    return pixels


def encode_chunky_to_planar(pixels: List[List[int]], width: int, height: int, depth: int) -> bytes:
    """
    Encode chunky pixel array to Amiga planar bitmap.
    Returns raw bitmap data (no header).
    """
    row_bytes = ((width + 15) // 16) * 2
    plane_size = row_bytes * height
    data = bytearray(plane_size * depth)

    for plane in range(depth):
        plane_offset = plane * plane_size
        for y in range(height):
            row_offset = plane_offset + y * row_bytes
            for x in range(width):
                if pixels[y][x] & (1 << plane):
                    byte_idx = row_offset + (x // 8)
                    bit_idx = 7 - (x % 8)
                    data[byte_idx] |= (1 << bit_idx)

    return bytes(data)


def export_icon_to_png(icon: ParsedIcon, icon_index: int, output_path: str,
                       transparency: str = "edge", force_planar: bool = False) -> bool:
    """
    Export an icon image to PNG file with configurable transparency.
    icon_index: 0 for main icon, 1 for select icon.
    transparency: "edge" = only edge-connected color 0, "all" = all color 0, "none" = opaque
    force_planar: if True, skip GlowIcons and export traditional planar images
    Returns True on success.

    Prefers GlowIcons (FORM ICON) when available as they are higher quality.
    Falls back to traditional planar images otherwise.
    """
    if not HAS_PNG:
        print("PNG export requires pypng library. Install with: pip install pypng", file=sys.stderr)
        return False

    # Try GlowIcons first (higher quality) unless --planar is specified
    if icon.glowicons and not force_planar:
        glow = parse_glowicons(icon.glowicons)
        if glow:
            # Check if we have the requested image
            if icon_index == 0:
                rgba = glow["rgba"]
                width = glow["width"]
                height = glow["height"]
            elif icon_index == 1 and glow.get("has_select"):
                rgba = glow["select_rgba"]
                width = glow.get("select_width", glow["width"])
                height = glow.get("select_height", glow["height"])
            else:
                rgba = None

            if rgba:
                # GlowIcons already have proper transparency from the IMAG/ARGB chunks
                # Convert to PNG rows
                rgba_rows = []
                for y in range(height):
                    row = []
                    for x in range(width):
                        offset = (y * width + x) * 4
                        row.extend([rgba[offset], rgba[offset+1], rgba[offset+2], rgba[offset+3]])
                    rgba_rows.append(row)

                with open(output_path, 'wb') as f:
                    writer = png.Writer(width=width, height=height, greyscale=False, alpha=True)
                    writer.write(f, rgba_rows)

                print(f"  (exported from GlowIcons FORM ICON data)")
                return True

    # Fall back to traditional planar images
    if not icon.main_icons_blob:
        print("No icon images in this file", file=sys.stderr)
        return False

    if icon_index >= icon.num_main_icons:
        print("Requested icon not present in file", file=sys.stderr)
        return False

    try:
        pos, width, height, depth, _ = get_icon_image_info(icon.main_icons_blob, icon_index)
    except ValueError as e:
        print(f"Error reading icon: {e}", file=sys.stderr)
        return False

    pixels = decode_planar_to_chunky(icon.main_icons_blob, pos, width, height, depth)

    # Choose palette based on depth and Workbench version
    # Deep icons (4+ planes) use the extended 16-color MagicWB palette
    if depth > 3:
        palette = PALETTE_16
    elif icon.revision >= 1:
        palette = WB20_COLORS
    else:
        palette = WB13_COLORS

    # Determine transparency based on mode
    if transparency == "edge":
        edge_transparent = find_edge_background(pixels, width, height)
    else:
        edge_transparent = None

    # Convert to RGBA rows for PNG
    rgba_rows = []
    for y in range(height):
        row = []
        for x in range(width):
            idx = pixels[y][x] % len(palette)
            r, g, b = palette[idx]
            # Apply transparency based on mode
            if transparency == "none":
                a = 255
            elif transparency == "all":
                a = 0 if idx == 0 else 255
            else:  # edge
                a = 0 if (idx == 0 and edge_transparent[y][x]) else 255
            row.extend([r, g, b, a])
        rgba_rows.append(row)

    with open(output_path, 'wb') as f:
        writer = png.Writer(width=width, height=height, greyscale=False, alpha=True)
        writer.write(f, rgba_rows)

    return True


def quantize_to_palette(r: int, g: int, b: int, palette: List[Tuple[int, int, int]]) -> Tuple[int, int]:
    """
    Find closest palette color using Euclidean distance.
    Returns (palette_index, squared_distance).
    """
    best_idx = 0
    best_dist = 0x7FFFFFFF
    for idx, (pr, pg, pb) in enumerate(palette):
        dist = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx, best_dist


def import_png_to_icon(icon: ParsedIcon, icon_index: int, png_path: str) -> bool:
    """
    Import a PNG file into an icon image slot.
    icon_index: 0 for main icon, 1 for select icon.
    Returns True on success.

    Supports RGBA PNGs - transparent pixels are mapped to color 0 (background).
    Automatically selects best palette (WB1.3, WB2.0, or 16-color MagicWB).
    """
    if not HAS_PNG:
        print("PNG import requires pypng library. Install with: pip install pypng", file=sys.stderr)
        return False

    if icon_index == 1 and icon.num_main_icons < 2:
        print("This icon has no select image slot", file=sys.stderr)
        return False

    # Read PNG
    try:
        reader = png.Reader(filename=png_path)
        width, height, rows, metadata = reader.read()
        rows = list(rows)  # Materialize the iterator
    except Exception as e:
        print(f"Error reading PNG: {e}", file=sys.stderr)
        return False

    has_alpha = metadata.get('alpha', False)
    pixel_size = 4 if has_alpha else 3

    # Check for transparency
    has_transparent_pixels = False
    if has_alpha:
        for row in rows:
            for x in range(width):
                offset = x * pixel_size + 3  # Alpha channel
                if row[offset] < 128:  # Semi-transparent or fully transparent
                    has_transparent_pixels = True
                    break
            if has_transparent_pixels:
                break

    # Quantize to all three palettes and pick best
    palettes = [
        ("WB1.3", WB13_COLORS, 3),
        ("WB2.0", WB20_COLORS, 3),
        ("16-color", PALETTE_16, 4),
    ]

    best_result = None
    best_max_dist = float('inf')
    best_palette_name = ""
    best_depth = 3

    for palette_name, palette, max_depth in palettes:
        pixels = [[0] * width for _ in range(height)]
        max_dist = 0

        for y, row in enumerate(rows):
            for x in range(width):
                offset = x * pixel_size
                r, g, b = row[offset], row[offset + 1], row[offset + 2]

                # Check for transparency
                if has_alpha:
                    a = row[offset + 3]
                    if a < 128:
                        # Transparent pixel -> color 0 (background)
                        pixels[y][x] = 0
                        continue

                idx, dist = quantize_to_palette(r, g, b, palette)
                pixels[y][x] = idx
                max_dist = max(max_dist, dist)

        if max_dist < best_max_dist:
            best_max_dist = max_dist
            best_result = pixels
            best_palette_name = palette_name
            # Determine depth based on max color index used
            max_color = max(max(row) for row in pixels)
            if max_color <= 1:
                best_depth = 1
            elif max_color <= 3:
                best_depth = 2
            elif max_color <= 7:
                best_depth = 3
            else:
                best_depth = 4

    pixels = best_result
    depth = best_depth

    print(f"Mapping to {best_palette_name} palette, depth={depth}, max_color_error={best_max_dist}")
    if has_transparent_pixels:
        print(f"Transparent pixels mapped to color 0 (background)")
    if best_max_dist > 1000:
        print("Warning: significant color error - consider adjusting source image")

    # Encode to planar format
    bitmap_data = encode_chunky_to_planar(pixels, width, height, depth)

    # Build new IMAGE header (20 bytes)
    header = bytearray(20)
    write_field(header, 0, 2, False, 0)       # LeftEdge
    write_field(header, 2, 2, False, 0)       # TopEdge
    write_field(header, 4, 2, False, width)   # Width
    write_field(header, 6, 2, False, height)  # Height
    write_field(header, 8, 2, False, depth)   # Depth
    write_field(header, 10, 4, False, 0x12345678)  # ImageData placeholder (non-zero)
    header[14] = (1 << depth) - 1             # PlanePick
    header[15] = 0                            # PlaneOnOff
    write_field(header, 16, 4, False, 0)      # NextImage

    new_icon_data = bytes(header) + bitmap_data

    # Rebuild main_icons_blob
    blob = bytearray(icon.main_icons_blob)
    if icon_index == 0:
        old_size = get_main_icon_size(blob, 0, strict=False)
        if icon.num_main_icons == 2:
            # Preserve select icon
            select_data = blob[old_size:]
            icon.main_icons_blob = new_icon_data + bytes(select_data)
        else:
            icon.main_icons_blob = new_icon_data
    else:
        # Replace select icon
        first_size = get_main_icon_size(blob, 0, strict=False)
        icon.main_icons_blob = bytes(blob[:first_size]) + new_icon_data

    # Update gadget dimensions if new icon is larger
    gadget_w = be_u16(icon.data, OFF_GADGET + 8)
    gadget_h = be_u16(icon.data, OFF_GADGET + 10)
    if width > gadget_w:
        put_be_u16(icon.data, OFF_GADGET + 8, width)
    if height > gadget_h:
        put_be_u16(icon.data, OFF_GADGET + 10, height)

    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Batch edit Amiga Workbench .info files: ToolTypes, icon position, structure fields, PNG import/export"
    )
    ap.add_argument("paths", nargs="+", help="Paths to .info files (or base names without .info)")

    # Listing / inspection
    ap.add_argument("--list", action="store_true", help="List parsed metadata + tooltypes")
    ap.add_argument("-v", "--verbose", action="store_true", help="With --list: dump full structure (all fields)")

    # ToolTypes operations
    ap.add_argument("--get", metavar="KEY", help="Get ToolType KEY. For booleans, prints KEY=true/false. Accepts KEY or (KEY).")
    ap.add_argument("--set", metavar="KEY=VAL", help="Set/replace ToolType KEY=VAL")
    ap.add_argument("--set-flag", metavar="KEY", help="Set boolean ToolType KEY (writes KEY)")
    ap.add_argument("--unset", metavar="KEY", help="Unset/disable boolean ToolType KEY (writes (KEY))")
    ap.add_argument("--delete", metavar="KEY", help="Delete ToolType KEY (removes KEY, (KEY), and KEY=VAL)")
    ap.add_argument("--normalize", action="store_true", help="Normalize tooltypes (last-wins per key, remove empties)")
    ap.add_argument("--ignore-case", action="store_true", help="Match keys case-insensitively")

    # Position and window
    ap.add_argument("--pos", metavar="X,Y", help="Set DiskObject CurrentX,CurrentY (icon placement)")
    ap.add_argument("--winsize", metavar="W,H", help="Disk/Drawer: set DrawerData NewWindow Width,Height")

    # Structure editing
    ap.add_argument("--edit", metavar="FIELD=VAL", action="append",
                    help="Edit structure field (e.g. DiskObject:Gadget:LeftEdge=100). Can be repeated.")

    # PNG import/export
    ap.add_argument("--export-icon", metavar="PATH", help="Export main icon to PNG file")
    ap.add_argument("--export-select-icon", metavar="PATH", help="Export select icon to PNG file")
    ap.add_argument("--import-icon", metavar="PATH", help="Import PNG file as main icon")
    ap.add_argument("--import-select-icon", metavar="PATH", help="Import PNG file as select icon")
    ap.add_argument("--transparency", choices=["edge", "all", "none"], default="edge",
                    help="Transparency mode for PNG export: 'edge' (default) = only edge-connected color 0, "
                         "'all' = all color 0 pixels, 'none' = no transparency")
    ap.add_argument("--planar", action="store_true",
                    help="Force export of planar images (skip GlowIcons even if present)")

    # Other options
    ap.add_argument("-o", "--output", metavar="PATH", help="Write to separate output file (non-destructive)")
    ap.add_argument("--compact", action="store_true", help="Rebuild file to compact segments (esp. ToolTypes)")
    ap.add_argument("--strict", action="store_true", help="Fail fast on suspicious lengths/bounds")
    ap.add_argument("--dry-run", action="store_true", help="Don't write, just show what would change")
    ap.add_argument("--backup", action="store_true", help="Write .bak backup once before modifying")
    args = ap.parse_args()

    has_operation = (args.list or args.get or args.set or args.set_flag or args.unset or
                     args.delete or args.normalize or args.pos or args.winsize or args.compact or
                     args.edit or args.export_icon or args.export_select_icon or
                     args.import_icon or args.import_select_icon)
    if not has_operation:
        ap.error("No operation specified")

    if args.output and len(args.paths) > 1:
        ap.error("--output can only be used with a single input file")

    op_set_kv = None
    if args.set:
        if "=" not in args.set:
            ap.error("--set requires KEY=VAL")
        k, v = args.set.split("=", 1)
        op_set_kv = (k, v)

    pos_xy = None
    if args.pos:
        if "," not in args.pos:
            ap.error("--pos requires X,Y")
        xs, ys = args.pos.split(",", 1)
        pos_xy = (int(xs, 0), int(ys, 0))

    win_wh = None
    if args.winsize:
        if "," not in args.winsize:
            ap.error("--winsize requires W,H")
        ws, hs = args.winsize.split(",", 1)
        win_wh = (int(ws, 0), int(hs, 0))

    rc = 0

    for p in args.paths:
        info_path = p if p.lower().endswith(".info") else p + ".info"
        try:
            icon = parse_icon_file(info_path, strict=args.strict)
        except Exception as e:
            print(f"{info_path}: ERROR: {e}", file=sys.stderr)
            rc = 2
            continue

        if args.list:
            print(f"{info_path}:")
            if args.verbose:
                # Full structure dump
                dump_icon_verbose(icon)
            else:
                # Compact summary
                print(f"  type: {icon.icon_type} ({icon_type_name(icon.icon_type)})")
                print(f"  version: {icon.version}, revision: {icon.revision}, main_icons: {icon.num_main_icons}")
                try:
                    cx = be_i32(icon.data, OFF_CURRENTX)
                    cy = be_i32(icon.data, OFF_CURRENTY)
                    print(f"  currentxy: {cx},{cy}")
                except Exception:
                    print("  currentxy: (unavailable)")
                w = be_u16(icon.data, OFF_MAIN_CANVAS_W)
                h = be_u16(icon.data, OFF_MAIN_CANVAS_H)
                print(f"  canvas: {w}x{h}")
                print(f"  has_drawerdata: {icon.has_drawerdata}  has_defaulttool: {icon.has_defaulttool}  has_tooltypes: {icon.has_tooltypes}  has_toolwindow: {icon.has_toolwindow}")
                if icon.has_tooltypes and icon.tooltypes_raw_entries:
                    for e in icon.tooltypes_raw_entries:
                        print(f"  {bytes_to_tt_str(e)}")
                else:
                    print("  (no tooltypes)")
            print()

        if args.get:
            want = canon_key(args.get)
            last: Optional[TTItem] = None
            for e in icon.tooltypes_raw_entries:
                item = parse_tt_item(bytes_to_tt_str(e))
                if key_eq(item.key, want, args.ignore_case):
                    last = item
            if last is None:
                print(f"{info_path}: {args.get} not set")
            else:
                if last.kind == "kv":
                    print(f"{info_path}: {want}={last.value}")
                else:
                    state = "false" if last.negated else "true"
                    print(f"{info_path}: {want}={state}")

        changed = False

        if pos_xy is not None:
            set_current_xy(icon, pos_xy[0], pos_xy[1])
            changed = True

        if win_wh is not None:
            ok = set_drawer_winsize(icon, win_wh[0], win_wh[1])
            if not ok:
                print(f"{info_path}: NOTE: --winsize ignored (no DrawerData in this icon)")
            else:
                changed = True

        # Structure editing (--edit)
        if args.edit:
            for edit_spec in args.edit:
                if apply_edit(icon, edit_spec):
                    changed = True
                else:
                    rc = 1

        # PNG export (read-only, no change to file)
        if args.export_icon:
            if export_icon_to_png(icon, 0, args.export_icon, args.transparency, args.planar):
                print(f"{info_path}: exported main icon to {args.export_icon}")
            else:
                rc = 1

        if args.export_select_icon:
            if export_icon_to_png(icon, 1, args.export_select_icon, args.transparency, args.planar):
                print(f"{info_path}: exported select icon to {args.export_select_icon}")
            else:
                rc = 1

        # PNG import
        if args.import_icon:
            if import_png_to_icon(icon, 0, args.import_icon):
                print(f"{info_path}: imported main icon from {args.import_icon}")
                changed = True
            else:
                rc = 1

        if args.import_select_icon:
            if import_png_to_icon(icon, 1, args.import_select_icon):
                print(f"{info_path}: imported select icon from {args.import_select_icon}")
                changed = True
            else:
                rc = 1

        new_tooltypes = None
        # Tool icons (type 3) can have tooltypes added even if they don't exist yet
        can_have_tooltypes = icon.has_tooltypes or icon.icon_type == 3
        if can_have_tooltypes and (op_set_kv or args.set_flag or args.unset or args.delete or args.normalize):
            existing_entries = icon.tooltypes_raw_entries if icon.has_tooltypes else []
            new_tooltypes = apply_tooltypes_ops(
                existing_entries,
                op_set_kv=op_set_kv,
                op_set_flag=args.set_flag,
                op_unset_flag=args.unset,
                op_del=args.delete,
                op_norm=args.normalize,
                ignore_case=args.ignore_case,
            )
            # Update has_tooltypes based on whether we end up with any entries
            had_tooltypes = icon.has_tooltypes
            will_have_tooltypes = len(new_tooltypes) > 0
            if had_tooltypes != will_have_tooltypes:
                icon.has_tooltypes = will_have_tooltypes
                # Update presence field in header (non-zero = has tooltypes)
                put_be_i32(icon.data, OFF_TOOLTYPES_PRESENCE, 1 if will_have_tooltypes else 0)
                changed = True
            if new_tooltypes != existing_entries:
                changed = True

        if changed or args.compact:
            new_bytes = rebuild_file(icon, new_tooltypes=new_tooltypes, compact=args.compact)

            # Determine output path
            out_path = args.output if args.output else info_path

            # Skip if no actual changes (only for in-place updates)
            if not args.output:
                old_bytes = open(info_path, "rb").read()
                if new_bytes == old_bytes:
                    continue

            if args.dry_run:
                if args.output:
                    print(f"{info_path}: would write to {out_path}")
                else:
                    print(f"{info_path}: would update")
                continue

            # Backup only for in-place updates
            if args.backup and not args.output:
                bak = info_path + ".bak"
                if not os.path.exists(bak):
                    shutil.copy2(info_path, bak)

            with open(out_path, "wb") as f:
                f.write(new_bytes)
            if args.output:
                print(f"{info_path}: wrote to {out_path}")
            else:
                print(f"{info_path}: updated")

    return rc

if __name__ == "__main__":
    raise SystemExit(main())

