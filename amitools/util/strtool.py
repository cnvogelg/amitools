import string

CTRL_CHAR_MAP = {"\t": "\\t", "\r": "\\r", "\n": "\\n"}


def to_text_string(txt, add_size=False):
    """convert a string to text representation but replace non-printable chars"""
    # replace non printable chars
    result = []
    for c in txt:
        if c in CTRL_CHAR_MAP:
            result.append(CTRL_CHAR_MAP[c])
        elif c in string.printable:
            # quote
            if c == "'":
                result.append("\\'")
            # regular char
            else:
                result.append(c)
        else:
            result.append(f"\\x{ord(c):02x}")
    new_txt = "".join(result)
    if add_size:
        return f"'{new_txt}'({len(txt)})"
    else:
        return f"'{new_txt}'"


def to_binary_string(txt, crop_after=8):
    """convert a string to binary and crop after a given number"""
    result = []
    num = 0
    ellipsis = False
    for c in txt:
        if c in string.printable and c not in CTRL_CHAR_MAP:
            result.append(f"'{c}'")
        else:
            result.append(f"{ord(c):02x}")
        num += 1
        if num >= crop_after:
            ellipsis = True
            break
    new_txt = " ".join(result)
    if ellipsis:
        new_txt += " ..."
    return f"{new_txt} ({len(txt)})"


def to_string(txt, txt_ratio=75, add_size=False):
    """convert a string to a human-readable representation"""
    printable = 0
    total = len(txt)
    for c in txt:
        if c in string.printable:
            printable += 1
    ratio = printable * 100 // total
    # if likely a text?
    if ratio >= txt_ratio:
        return to_text_string(txt, add_size)
    else:
        return to_binary_string(txt)
