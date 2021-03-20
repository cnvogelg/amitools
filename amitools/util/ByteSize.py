"""tools to convert byte sizes into strings suitable for disk/file sizes"""

KIB_UNIT = 1024

# map unit extension to power of 1000/KIB_UNIT
scale_map = {"k": 1, "m": 2, "g": 3, "t": 4}


def to_byte_size_str(size, kibi_units=True):
    """convert a byte value into a 5 letter string"""
    if kibi_units:
        unit = KIB_UNIT
        marker = "i"
    else:
        unit = 1000
        marker = ""
    if size < 1000:
        return "%3dB%s" % (size, marker)
    else:
        # run through scales
        for scale in "KMGT":
            next = size // unit
            if next < 10:
                frac = float(size) / unit
                if frac > 9.9:
                    frac = 9.9
                return "%3.1f%s%s" % (frac, scale, marker)
            elif next < 1000:
                return "%3d%s%s" % (next, scale, marker)
            size = next
        return "NaNB%s" % marker


def parse_byte_size_str(s):
    """parse a string to derive a byte value.
    can read e.g. 10Ki, 2.1k or 2048.
    returns None if the string is invalid or a byte value
    """
    s = s.lower()
    n = len(s)
    if n == 0:
        return None
    # 'i' - use Kibi units
    if s[-1] == "i":
        unit = KIB_UNIT
        if n == 1:
            return None
        s = s[:-1]
        n -= 1
    # else Si units
    else:
        unit = 1000
    # check for scale
    scale = s[-1]
    if scale in list(scale_map.keys()):
        factor = unit ** scale_map[scale]
        if n == 1:
            return None
        s = s[:-1]
        n -= 1
    else:
        factor = 1
    # get number
    try:
        v = int(float(s) * factor)
        return v
    except ValueError:
        return None


# a small test
if __name__ == "__main__":
    import sys

    for a in sys.argv[1:]:
        v = parse_byte_size_str(a)
        if v != None:
            print(
                (a, ":", v, "=", to_byte_size_str(v), "=", to_byte_size_str(v, False))
            )
        else:
            print((a, ":", v))
