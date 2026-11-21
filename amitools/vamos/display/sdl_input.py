"""Translate SDL keyboard events to classic Amiga input codes."""

from functools import lru_cache


@lru_cache(maxsize=1)
def raw_key_map():
    import sdl2

    # Physical positions on the classic keyboard, independent of host symbols.
    rows = [
        (0x00, "GRAVE 1 2 3 4 5 6 7 8 9 0 MINUS EQUALS BACKSLASH"),
        (0x10, "Q W E R T Y U I O P LEFTBRACKET RIGHTBRACKET"),
        (0x20, "A S D F G H J K L SEMICOLON APOSTROPHE NONUSHASH"),
        (0x30, "NONUSBACKSLASH Z X C V B N M COMMA PERIOD SLASH"),
        (0x40, "SPACE BACKSPACE TAB KP_ENTER RETURN ESCAPE DELETE"),
        (0x4C, "UP DOWN RIGHT LEFT"),
        (0x50, "F1 F2 F3 F4 F5 F6 F7 F8 F9 F10"),
        (0x5C, "KP_DIVIDE KP_MULTIPLY KP_PLUS HELP"),
        (0x60, "LSHIFT RSHIFT CAPSLOCK LCTRL LALT RALT LGUI RGUI"),
    ]
    result = {
        getattr(sdl2, "SDL_SCANCODE_" + name): start + index
        for start, names in rows
        for index, name in enumerate(names.split())
    }
    for digit, code in enumerate(
        (0x0F, 0x1D, 0x1E, 0x1F, 0x2D, 0x2E, 0x2F, 0x3D, 0x3E, 0x3F)
    ):
        result[getattr(sdl2, "SDL_SCANCODE_KP_" + str(digit))] = code
    result[sdl2.SDL_SCANCODE_KP_PERIOD] = 0x3C
    result[sdl2.SDL_SCANCODE_KP_MINUS] = 0x4A
    result[sdl2.SDL_SCANCODE_RCTRL] = 0x63
    return result


def translate_key(keysym, released=False, repeat=False, vanilla=False):
    """Return (is_vanilla, code, qualifier), or None for an unmapped key.

    Printable SDL symbols use the host layout; shift punctuation follows
    the US layout until guest keymap.library conversion is available.
    """
    import sdl2

    mod = keysym.mod
    qualifier = sum(
        bit
        for mask, bit in (
            (sdl2.KMOD_LSHIFT, 1),
            (sdl2.KMOD_RSHIFT, 2),
            (sdl2.KMOD_CAPS, 4),
            (sdl2.KMOD_CTRL, 8),
            (sdl2.KMOD_LALT, 16),
            (sdl2.KMOD_RALT, 32),
            (sdl2.KMOD_LGUI, 64),
            (sdl2.KMOD_RGUI, 128),
        )
        if mod & mask
    )
    if repeat:
        qualifier |= 0x200
    raw = raw_key_map().get(keysym.scancode)
    if raw in (
        0x0F,
        0x1D,
        0x1E,
        0x1F,
        0x2D,
        0x2E,
        0x2F,
        0x3D,
        0x3E,
        0x3F,
        0x3C,
        0x43,
        0x4A,
        0x5C,
        0x5D,
        0x5E,
    ):
        qualifier |= 0x100
    code = keysym.sym
    if vanilla and (32 <= code <= 255 or code in (8, 9, 13, 27)):
        if released:
            return None
        char = chr(code)
        shift, caps = bool(mod & sdl2.KMOD_SHIFT), bool(mod & sdl2.KMOD_CAPS)
        if char.isalpha() and shift != caps:
            upper = char.upper()
            if len(upper) == 1 and ord(upper) <= 255:
                code = ord(upper)
        elif shift:
            plain = "`1234567890-=[]\\;',./"
            shifted = '~!@#$%^&*()_+{}|:"<>?'
            if char in plain:
                code = ord(shifted[plain.index(char)])
        if mod & sdl2.KMOD_CTRL and (64 <= code <= 95 or 97 <= code <= 122):
            code &= 31
        return True, code, qualifier
    if raw is None:
        return None
    return False, raw | (0x80 if released else 0), qualifier
