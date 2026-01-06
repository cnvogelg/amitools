from amitools.vamos.astructs.astructdef import AmigaStructDef
from amitools.vamos.astructs.astruct import AmigaStruct
from amitools.vamos.astructs.scalar import ULONG, UWORD, UBYTE, WORD, BYTE
from amitools.vamos.astructs.array import ARRAY
from amitools.vamos.libstructs.exec_ import SignalSemaphoreStruct, MinListStruct

#------ Font Styles (bit flags) -------
FSF_UNDERLINED = 0x01
FSF_BOLD       = 0x02
FSF_ITALIC     = 0x04
FSF_EXTENDED   = 0x08
FSF_COLORFONT  = 0x40
FSF_TAGGED     = 0x80

#------ Font Flags (bit flags) -------
FPF_ROMFONT     = 0x01
FPF_DISKFONT    = 0x02
FPF_REVPATH     = 0x04
FPF_TALLDOT     = 0x08
FPF_WIDEDOT     = 0x10
FPF_PROPORTIONAL= 0x20
FPF_DESIGNED    = 0x40
FPF_REMOVED     = 0x80

@AmigaStructDef
class TextAttrStruct(AmigaStruct):
    _format = [
        (ULONG, "ta_Name"),   # STRPTR to font name
        (UWORD, "ta_YSize"),  # font height
        (UBYTE, "ta_Style"),  # style flags
        (UBYTE, "ta_Flags"),  # font flags
    ]

@AmigaStructDef
class TTextAttrStruct(AmigaStruct):
    _format = [
        (ULONG, "tta_Name"),   # STRPTR to font name
        (UWORD, "tta_YSize"),  # font height
        (UBYTE, "tta_Style"),  # style flags
        (UBYTE, "tta_Flags"),  # font flags
        (ULONG, "tta_Tags"),   # pointer to TagItem list
    ]

@AmigaStructDef
class BitMapStruct(AmigaStruct):
    _format = [
        (UWORD, "BytesPerRow"),
        (UWORD, "Rows"),
        (UBYTE, "Flags"),
        (UBYTE, "Depth"),
        (UWORD, "pad"),

        # Explicitly define each bitplane pointer
        (ARRAY(ULONG, 8), "Planes"),  # PLANEPTR
    ]


@AmigaStructDef
class RastPortStruct(AmigaStruct):
    _format = [
        (ULONG, "Layer"),           # struct Layer*
        (ULONG, "BitMap"),          # struct BitMap*
        (ULONG, "AreaPtrn"),        # UWORD*
        (ULONG, "TmpRas"),          # struct TmpRas*
        (ULONG, "AreaInfo"),        # struct AreaInfo*
        (ULONG, "GelsInfo"),        # struct GelsInfo*

        (UBYTE, "Mask"),
        (BYTE, "FgPen"),
        (BYTE, "BgPen"),
        (BYTE, "AOlPen"),
        (BYTE, "DrawMode"),
        (BYTE, "AreaPtSz"),
        (BYTE, "linpatcnt"),
        (BYTE, "dummy"),

        (UWORD, "Flags"),
        (UWORD, "LinePtrn"),

        (WORD, "cp_x"),
        (WORD, "cp_y"),

        (ARRAY(UBYTE, 8), "minterms"),

        (WORD, "PenWidth"),
        (WORD, "PenHeight"),

        (ULONG, "Font"),            # struct TextFont*

        (UBYTE, "AlgoStyle"),
        (UBYTE, "TxFlags"),
        (UWORD, "TxHeight"),
        (UWORD, "TxWidth"),
        (UWORD, "TxBaseline"),
        (WORD, "TxSpacing"),

        (ULONG, "RP_User"),         # APTR*
    ]

@AmigaStructDef
class RectangleStruct(AmigaStruct):
    _format = [
        (WORD, "MinX"),
        (WORD, "MinY"),
        (WORD, "MaxX"),
        (WORD, "MaxY"),
    ]


@AmigaStructDef
class RegionRectangleStruct(AmigaStruct):
    _format = [
        (ULONG, "Next"),     # struct RegionRectangle*
        (ULONG, "Prev"),     # struct RegionRectangle*
        (RectangleStruct, "bounds"),
    ]

@AmigaStructDef
class RegionStruct(AmigaStruct):
    _format = [
        (RectangleStruct, "bounds"),
        (ULONG, "RegionRectangle"),   # struct RegionRectangle*
    ]

@AmigaStructDef
class LayerInfoStruct(AmigaStruct):
    _format = [
        (ULONG, "top_layer"),            # struct Layer*
        (ULONG, "resPtr1"),              # void* (V45 spare)
        (ULONG, "resPtr2"),              # void* (V45 spare)
        (ULONG, "FreeClipRects"),        # struct ClipRect*

        (RectangleStruct, "bounds"),     # struct Rectangle

        (SignalSemaphoreStruct, "Lock"), # struct SignalSemaphore
        (MinListStruct, "gs_Head"),      # struct MinList

        (WORD, "PrivateReserve3"),       # Private
        (ULONG, "PrivateReserve4"),      # Private

        (UWORD, "Flags"),
        (BYTE, "res_count"),             # V45 spare
        (BYTE, "LockLayersCount"),
        (BYTE, "PrivateReserve5"),       # Private
        (BYTE, "UserClipRectsCount"),    # Private

        (ULONG, "BlankHook"),            # struct Hook*
        (ULONG, "resPtr5"),              # Private
    ]

@AmigaStructDef
class ViewPortStruct(AmigaStruct):
    _format = [
        (ULONG, "Next"),              # struct ViewPort*
        (ULONG, "ColorMap"),          # struct ColorMap*
        (ULONG, "DspIns"),            # struct CopList*
        (ULONG, "SprIns"),            # struct CopList*
        (ULONG, "ClrIns"),            # struct CopList*
        (ULONG, "UCopIns"),           # struct UCopList*

        (WORD, "DWidth"),
        (WORD, "DHeight"),
        (WORD, "DxOffset"),
        (WORD, "DyOffset"),

        (UWORD, "Modes"),
        (UBYTE, "SpritePriorities"),
        (UBYTE, "ExtendedModes"),

        (ULONG, "RasInfo"),           # struct RasInfo*
    ]

@AmigaStructDef
class LayerStruct(AmigaStruct):
    _format = [
        (ULONG, "front"),
        (ULONG, "back"),
        (ULONG, "ClipRect"),
        (ULONG, "rp"),
        (RectangleStruct, "bounds"),
        (ULONG, "nlink"),
        (UWORD, "priority"),
        (UWORD, "Flags"),
        (ULONG, "SuperBitMap"),
        (ULONG, "SuperClipRect"),
        (ULONG, "Window"),
        (WORD, "Scroll_X"),
        (WORD, "Scroll_Y"),
        (ULONG, "OnScreen"),
        (ULONG, "OffScreen"),
        (ULONG, "Backup"),
        (ULONG, "SuperSaveClipRects"),
        (ULONG, "Undamaged"),
        (ULONG, "LayerInfo"),
        (SignalSemaphoreStruct, "Lock"),
        (ULONG, "BackFill"),
        (ULONG, "reserved1"),
        (ULONG, "ClipRegion"),
        (ULONG, "clipped"),
        (WORD, "Width"),
        (WORD, "Height"),
        # 18 bytes
        (ULONG, "reserved2"),
        (ULONG, "reserved2a"),
        (ULONG, "reserved2b"),
        (ULONG, "reserved2c"),
        (UWORD, "reserved2d"),

        # ⭐ Correct: pointer to Region, not embedded RegionStruct
        (ULONG, "DamageList"),
    ]

