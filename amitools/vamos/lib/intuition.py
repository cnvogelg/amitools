from amitools.vamos.astructs.astruct import AmigaStruct
from amitools.vamos.astructs.astructdef import AmigaStructDef
from amitools.vamos.astructs.scalar import ULONG, WORD, UWORD, BYTE, UBYTE, LONG
from amitools.vamos.astructs.string import CSTR
from amitools.vamos.libstructs.exec_ import MessageStruct
from amitools.vamos.lib.graphics import RastPortStruct, BitMapStruct, LayerInfoStruct, ViewPortStruct


# TAGS
TAG_USER       = 0x80000000
WA_Dummy       = TAG_USER + 99  # 0x80000063

WA_Left        = WA_Dummy + 0x01
WA_Top         = WA_Dummy + 0x02
WA_Width       = WA_Dummy + 0x03
WA_Height      = WA_Dummy + 0x04
WA_DetailPen   = WA_Dummy + 0x05
WA_BlockPen    = WA_Dummy + 0x06
WA_IDCMP       = WA_Dummy + 0x07
WA_Flags       = WA_Dummy + 0x08
WA_Gadgets     = WA_Dummy + 0x09
WA_Checkmark   = WA_Dummy + 0x0A
WA_Title       = WA_Dummy + 0x0B
WA_ScreenTitle = WA_Dummy + 0x0C
WA_CustomScreen= WA_Dummy + 0x0D
WA_SuperBitMap = WA_Dummy + 0x0E
WA_MinWidth    = WA_Dummy + 0x0F
WA_MinHeight   = WA_Dummy + 0x10
WA_MaxWidth    = WA_Dummy + 0x11
WA_MaxHeight   = WA_Dummy + 0x12

@AmigaStructDef
class NewWindowStruct(AmigaStruct):
    _format = [
        (WORD,  "LeftEdge"),
        (WORD,  "TopEdge"),
        (WORD,  "Width"),
        (WORD,  "Height"),
        (UBYTE, "DetailPen"),
        (UBYTE, "BlockPen"),
        (ULONG, "IDCMPFlags"),
        (ULONG, "Flags"),
        (ULONG, "FirstGadget"),   # pointer to Gadget struct
        (ULONG, "CheckMark"),     # pointer to Image struct
        (ULONG, "Title"),         # pointer to string
        (ULONG, "Screen"),        # pointer to Screen struct
        (ULONG, "BitMap"),        # pointer to BitMap struct
        (WORD,  "MinWidth"),
        (WORD,  "MinHeight"),
        (UWORD, "MaxWidth"),
        (UWORD, "MaxHeight"),
        (UWORD, "Type"),
    ]

@AmigaStructDef
class WindowStruct(AmigaStruct):
    _format = [
        (ULONG, "NextWindow"),         # struct Window* NextWindow

        (WORD, "LeftEdge"),
        (WORD, "TopEdge"),
        (WORD, "Width"),
        (WORD, "Height"),

        (WORD, "MouseY"),
        (WORD, "MouseX"),

        (WORD, "MinWidth"),
        (WORD, "MinHeight"),
        (UWORD, "MaxWidth"),
        (UWORD, "MaxHeight"),

        (ULONG, "Flags"),

        (ULONG, "MenuStrip"),          # struct Menu*
        (CSTR, "Title"),              # STRPTR

        (ULONG, "FirstRequest"),       # struct Requester*
        (ULONG, "DMRequest"),          # struct Requester*
        (WORD, "ReqCount"),

        (ULONG, "WScreen"),            # struct Screen*
        (ULONG, "RPort"),              # struct RastPort*

        (BYTE, "BorderLeft"),
        (BYTE, "BorderTop"),
        (BYTE, "BorderRight"),
        (BYTE, "BorderBottom"),
        (ULONG, "BorderRPort"),        # struct RastPort*

        (ULONG, "FirstGadget"),        # struct Gadget*
        (ULONG, "Parent"),             # struct Window*
        (ULONG, "Descendant"),         # struct Window*

        (ULONG, "Pointer"),            # UWORD*
        (BYTE, "PtrHeight"),
        (BYTE, "PtrWidth"),
        (BYTE, "XOffset"),
        (BYTE, "YOffset"),

        (ULONG, "IDCMPFlags"),
        (ULONG, "UserPort"),           # struct MsgPort*
        (ULONG, "WindowPort"),         # struct MsgPort*
        (ULONG, "MessageKey"),         # struct IntuiMessage*

        (UBYTE, "DetailPen"),
        (UBYTE, "BlockPen"),

        (ULONG, "CheckMark"),          # struct Image*
        (ULONG, "ScreenTitle"),        # STRPTR

        (WORD, "GZZMouseX"),
        (WORD, "GZZMouseY"),
        (WORD, "GZZWidth"),
        (WORD, "GZZHeight"),

        (ULONG, "ExtData"),            # UBYTE*
        (ULONG, "UserData"),           # BYTE*

        (ULONG, "WLayer"),             # struct Layer*
        (ULONG, "IFont"),              # struct TextFont*

        (ULONG, "MoreFlags"),
    ]

# IDCMP flags for Intuition event handling

IDCMP_SIZEVERIFY       = 0x00000001
IDCMP_NEWSIZE          = 0x00000002
IDCMP_REFRESHWINDOW    = 0x00000004
IDCMP_MOUSEBUTTONS     = 0x00000008
IDCMP_MOUSEMOVE        = 0x00000010
IDCMP_GADGETDOWN       = 0x00000020
IDCMP_GADGETUP         = 0x00000040
IDCMP_REQSET           = 0x00000080
IDCMP_MENUPICK         = 0x00000100
IDCMP_CLOSEWINDOW      = 0x00000200
IDCMP_RAWKEY           = 0x00000400
IDCMP_REQVERIFY        = 0x00000800
IDCMP_REQCLEAR         = 0x00001000
IDCMP_MENUVERIFY       = 0x00002000
IDCMP_NEWPREFS         = 0x00004000
IDCMP_DISKINSERTED     = 0x00008000
IDCMP_DISKREMOVED      = 0x00010000
IDCMP_WBENCHMESSAGE    = 0x00020000  # System use only
IDCMP_ACTIVEWINDOW     = 0x00040000
IDCMP_INACTIVEWINDOW   = 0x00080000
IDCMP_DELTAMOVE        = 0x00100000
IDCMP_VANILLAKEY       = 0x00200000
IDCMP_INTUITICKS       = 0x00400000
IDCMP_IDCMPUPDATE      = 0x00800000  # new for V36
IDCMP_MENUHELP         = 0x01000000  # new for V36
IDCMP_CHANGEWINDOW     = 0x02000000  # new for V36
IDCMP_GADGETHELP       = 0x04000000  # new for V39
IDCMP_EXTENDEDMOUSE    = 0x08000000  # new for V47 & V51
    
@AmigaStructDef
class IntuiMessageStruct(AmigaStruct):
    _format = [
        (MessageStruct, "ExecMessage"),
        (ULONG, "Class"),        # event class
        (UWORD, "Code"),         # event code
        (UWORD, "Qualifier"),    # e.g. shift/ctrl keys
        (ULONG, "IAddress"),     # optional pointer to source
        (WORD,  "MouseX"),
        (WORD,  "MouseY"),
        (ULONG, "Seconds"),      # 
        (ULONG, "Micros"),       # 
        (ULONG, "IDCMPWindow"),  # pointer to WindowStruct
        (ULONG, "SpecialLink"),  # pointer to WindowStruct
    ]

@AmigaStructDef
class MenuStruct(AmigaStruct):
    _format = [
        (ULONG, "NextMenu"),         # pointer to next menu at same level
        (WORD,  "LeftEdge"),
        (WORD,  "TopEdge"),
        (WORD,  "Width"),
        (WORD,  "Height"),
        (UWORD, "Flags"),
        (ULONG, "MenuName"),         # pointer to string
        (ULONG, "FirstItem"),        # pointer to first MenuItem

        # Internal use only
        (WORD,  "JazzX"),
        (WORD,  "JazzY"),
        (WORD,  "BeatX"),
        (WORD,  "BeatY"),
    ]

@AmigaStructDef
class MenuItemStruct(AmigaStruct):
    _format = [
        (ULONG, "NextItem"),         # pointer to next item
        (WORD,  "LeftEdge"),
        (WORD,  "TopEdge"),
        (WORD,  "Width"),
        (WORD,  "Height"),
        (UWORD, "Flags"),
        (LONG,  "MutualExclude"),
        (ULONG, "ItemFill"),         # pointer to Image, IntuiText, or NULL
        (ULONG, "SelectFill"),       # alternate image when highlighted
        (BYTE,  "Command"),          # command sequence byte
        (UBYTE, "__align1"),
        (ULONG, "SubItem"),          # pointer to submenu MenuItem
        (UWORD, "NextSelect"),
    ]

@AmigaStructDef
class IntuiTextStruct(AmigaStruct):
    _format = [
        (UBYTE, "FrontPen"),       # pen number for foreground
        (UBYTE, "BackPen"),        # pen number for background
        (UBYTE, "DrawMode"),       # rendering mode
        (UBYTE, "__align1"),
        (WORD,  "LeftEdge"),       # relative X position
        (WORD,  "TopEdge"),        # relative Y position
        (ULONG, "ITextFont"),      # pointer to TextAttr or NULL
        (ULONG, "IText"),          # pointer to null-terminated string
        (ULONG, "NextText"),       # pointer to next IntuiTextStruct
    ]

@AmigaStructDef
class TextFontStruct(AmigaStruct):
    _format = [
        (MessageStruct, "tf_Message"),   # reply message for font removal

        (UWORD, "tf_YSize"),             # font height
        (UBYTE, "tf_Style"),             # font style
        (UBYTE, "tf_Flags"),             # preferences and flags
        (UWORD, "tf_XSize"),             # nominal font width
        (UWORD, "tf_Baseline"),          # top of char to baseline
        (UWORD, "tf_BoldSmear"),         # smear for bold enhancement

        (UWORD, "tf_Accessors"),         # access count

        (UBYTE, "tf_LoChar"),            # first character
        (UBYTE, "tf_HiChar"),            # last character
        (ULONG, "tf_CharData"),          # pointer to bit character data

        (UWORD, "tf_Modulo"),            # row modulo for strike font
        (ULONG, "tf_CharLoc"),           # pointer to location data
        (ULONG, "tf_CharSpace"),         # pointer to spacing data
        (ULONG, "tf_CharKern"),          # pointer to kerning data
    ]
    
@AmigaStructDef
class ScreenStruct(AmigaStruct):
    _format = [
        (ULONG, "NextScreen"),       # struct Screen*
        (ULONG, "FirstWindow"),      # struct Window*

        (WORD, "LeftEdge"),
        (WORD, "TopEdge"),
        (WORD, "Width"),
        (WORD, "Height"),

        (WORD, "MouseY"),
        (WORD, "MouseX"),

        (UWORD, "Flags"),

        (ULONG, "Title"),            # UBYTE* (STRPTR)
        (ULONG, "DefaultTitle"),     # UBYTE* (STRPTR)

        # Bar dimensions
        (BYTE, "BarHeight"),
        (BYTE, "BarVBorder"),
        (BYTE, "BarHBorder"),
        (BYTE, "MenuVBorder"),
        (BYTE, "MenuHBorder"),
        (BYTE, "WBorTop"),
        (BYTE, "WBorLeft"),
        (BYTE, "WBorRight"),
        (BYTE, "WBorBottom"),
        (BYTE, "__align1"),

        (ULONG, "Font"),             # struct TextAttr*

        # Display structures
        (ViewPortStruct, "ViewPort"),    # struct ViewPort
        (RastPortStruct, "RastPort"),    # struct RastPort
        (BitMapStruct, "BitMap"),        # struct BitMap
        (LayerInfoStruct, "LayerInfo"),  # struct Layer_Info

        (ULONG, "FirstGadget"),      # struct Gadget*

        (UBYTE, "DetailPen"),
        (UBYTE, "BlockPen"),

        (UWORD, "SaveColor0"),

        (ULONG, "BarLayer"),         # struct Layer*

        (ULONG, "ExtData"),          # UBYTE*
        (ULONG, "UserData"),         # UBYTE*
    ]

@AmigaStructDef
class NewScreenStruct(AmigaStruct):
    _format = [
        (WORD,  "LeftEdge"),       # screen position X
        (WORD,  "TopEdge"),        # screen position Y
        (WORD,  "Width"),          # screen width
        (WORD,  "Height"),         # screen height
        (WORD,  "Depth"),          # number of bitplanes

        (UBYTE, "DetailPen"),      # pen for details
        (UBYTE, "BlockPen"),       # pen for blocks

        (UWORD, "ViewModes"),      # viewport modes
        (UWORD, "Type"),           # screen type flags

        (ULONG, "Font"),           # pointer to TextAttr
        (ULONG, "DefaultTitle"),   # pointer to title string
        (ULONG, "Gadgets"),        # pointer to Gadget (unused)
        (ULONG, "CustomBitMap"),   # pointer to BitMap
    ]
