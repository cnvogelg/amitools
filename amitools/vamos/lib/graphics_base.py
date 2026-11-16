"""Public GfxBase fields at their graphics/gfxbase.h ABI offsets."""

from amitools.vamos.astructs import (
    ARRAY,
    UBYTE,
    ULONG,
    UWORD,
    AmigaStruct,
    AmigaStructDef,
)
from amitools.vamos.libstructs import LibraryStruct, ListStruct


@AmigaStructDef
class GfxBaseStruct(AmigaStruct):
    # Reserve unimplemented private state as well: a V47 GfxBase is 552
    # bytes. Library-only allocation let clients read adjacent allocations.
    _format = [
        (LibraryStruct, "LibNode"),
        (ARRAY(UBYTE, 106), "private_22"),
        (ListStruct, "TextFonts"),  # 140
        (ULONG, "DefaultFont"),  # 154
        (ARRAY(UBYTE, 48), "private_9e"),
        (UWORD, "DisplayFlags"),  # 206
        (ARRAY(UBYTE, 8), "private_d0"),
        (UWORD, "NormalDisplayRows"),  # 216
        (UWORD, "NormalDisplayColumns"),  # 218
        (ARRAY(UBYTE, 12), "private_dc"),
        (UWORD, "MicrosPerLine"),  # 232
        (UWORD, "MinDisplayColumn"),
        (UBYTE, "ChipRevBits0"),  # 236
        (ARRAY(UBYTE, 315), "private_ed"),
    ]
