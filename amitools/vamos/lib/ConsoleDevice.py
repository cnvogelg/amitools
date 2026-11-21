"""Headless console.device unit -1 with a basic US raw-key map."""

from amitools.vamos.libcore import LibImpl


# Physical Amiga raw-key positions. Unsupported layout-specific and extended
# keys deliberately have no mapping; this is not a host keyboard translator.
_PLAIN = {
    base + offset: char
    for base, row in (
        (0x00, "`1234567890-=\\"),
        (0x10, "qwertyuiop[]"),
        (0x20, "asdfghjkl;'"),
        (0x31, "zxcvbnm,./"),
    )
    for offset, char in enumerate(row)
}
_PLAIN.update(
    {
        0x40: " ",
        0x41: "\b",
        0x42: "\t",
        0x43: "\r",
        0x44: "\r",
        0x45: "\x1b",
        0x46: "\x7f",
    }
)
_SHIFTED = dict(zip("`1234567890-=\\[];',./", '~!@#$%^&*()_+|{}:"<>?'))


class ConsoleDevice(LibImpl):
    def open_dev(self, ctx, request, unit, flags):
        # Unit -1 exposes the conversion vectors without opening a window.
        return 0 if unit & 0xFFFFFFFF == 0xFFFFFFFF else -1

    def RawKeyConvert(self, ctx, events, buffer, length, keyMap):
        # Explicit keymaps and dead-key/Alt combinations are outside this
        # subset. Report no conversion rather than substitute the US layout.
        if keyMap:
            return 0
        length &= 0xFFFFFFFF
        if length & 0x80000000:
            return -1
        output = bytearray()
        seen = set()
        while events:
            if events in seen:
                return -1
            seen.add(events)
            mem = ctx.mem
            code, qualifier = mem.r16(events + 6), mem.r16(events + 8)
            if mem.r8(events + 4) == 1 and not code & 0x80 and not qualifier & 0x30:
                char = _PLAIN.get(code)
                if char is not None:
                    if char.isalpha():
                        if qualifier & 7:  # Shift or Caps Lock
                            char = char.upper()
                    elif qualifier & 3:
                        char = _SHIFTED.get(char, char)
                    if qualifier & 8 and 64 <= ord(char.upper()) <= 95:
                        char = chr(ord(char.upper()) & 31)
                    if len(output) >= length:
                        return -1
                    output.append(ord(char))
            events = mem.r32(events)
        if output:
            if not buffer:
                return -1
            ctx.mem.w_block(buffer, bytes(output))
        return len(output)
