"""Regenerate the 8-pixel bitmap from the MIT-licensed TopazDouble source.

Run from the repository root:
  python -m amitools.vamos.lib.fonts.convert_topaz source/16 output.json
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from amitools.binfmt.BinFmt import BinFmt
from amitools.binfmt.Relocate import Relocate


def convert(source):
    image = Relocate(BinFmt().load_image(str(source))).relocate_one_block(0)
    # Return stub (4), DiskFontHeader prefix (54), TextFont message (20).
    fields = struct.unpack_from(">HBBHHHHBBIHIII", image, 78)
    (
        height,
        _style,
        _flags,
        width,
        baseline,
        bold,
        _,
        low,
        high,
        data,
        stride,
        loc,
        space,
        kern,
    ) = fields
    if height != 16 or width != 8 or low != 32 or high != 255 or space or kern:
        raise ValueError("expected the fixed-width 8x16 TopazDouble font")
    rows = [
        image[data + row * stride : data + (row + 1) * stride] for row in range(height)
    ]
    if any(rows[row] != rows[row + 1] for row in range(0, height, 2)):
        raise ValueError("glyph rows are not exact pairs; refusing a lossy conversion")
    locations = list(struct.unpack_from(">225I", image, loc))
    return {
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "height": height // 2,
        "width": width,
        "baseline": baseline // 2,
        "bold_smear": max(1, bold // 2),
        "low": low,
        "high": high,
        "modulo": stride,
        "locations": locations,
        "data": b"".join(rows[::2]).hex(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(convert(args.source), indent=2) + "\n")


if __name__ == "__main__":
    main()
