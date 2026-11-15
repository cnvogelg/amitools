Topaz-compatible 8x8 bitmap
=========================

Source: https://github.com/amigavision/TopazDouble
Revision: c7eb6f8fe40b8f0533ee3f5e76b7f28ea43e8ee8
Original path: Fonts/Topaz Double Sans/16
Copyright (c) 2024 Alex Limi. MIT license; see TopazDouble-LICENSE.txt.

TopazDoubleSans-16.hunk is the unmodified upstream Amiga disk font.
TopazDoubleSans-8.json is a modified, eight-pixel-high version. Every pair
of source bitmap rows is identical. The conversion removes one row from
each pair and halves the baseline and bold smear; the glyphs and their
locations are otherwise unchanged. This is a recreation, not a ROM dump.

Regenerate from the repository root:

python -m amitools.vamos.lib.fonts.convert_topaz \
  amitools/vamos/lib/fonts/TopazDoubleSans-16.hunk \
  amitools/vamos/lib/fonts/TopazDoubleSans-8.json

The converter refuses input that cannot be reduced losslessly. Its output
records the source SHA-256. The bundled bitmap serves topaz.font size 8.
Other requested sizes/styles currently use the licensed Cousine fallback.
