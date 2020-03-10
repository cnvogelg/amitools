# amitools utility functions


def _get_vis_char(d):
    if d >= 32 and d < 127:
        return "%c" % d
    else:
        return "."


def get_hex_line(addr, line, indent=0, num=16):
    l = len(line)
    skip = num - l
    out = " " * indent
    out += "%08x: " % addr
    for d in line:
        out += "%02x " % d
    for d in range(skip):
        out += "   "
    out += " "
    for d in line:
        out += _get_vis_char(d)
    return out


def print_hex(data, indent=0, num=16, out=print, base_addr=0):
    l = len(data)
    o = 0
    addr = base_addr
    while o < l:
        line = data[o : o + num]
        out(get_hex_line(addr, line, indent, num))
        o += num
        addr += num


def get_hex_diff_line(addr, a_line, b_line, indent=0, num=16):
    na = len(a_line)
    nb = len(b_line)
    n = max(na, nb)
    skip = num - n
    out = " " * indent
    out += "%08x: " % addr
    ah = []
    ac = []
    bh = []
    bc = []
    for d in range(n):
        av = a_line[d]
        bv = b_line[d]
        if av != bv:
            ah.append("%02x" % av)
            ac.append(_get_vis_char(av))
            bh.append("%02x" % bv)
            bc.append(_get_vis_char(bv))
        else:
            ah.append("--")
            ac.append(" ")
            bh.append("--")
            bc.append(" ")
    for d in range(skip):
        ah.append("  ")
        ac.append(" ")
        bh.append("  ")
        bc.append(" ")
    out += " ".join(ah) + "  " + "".join(ac) + " | "
    out += " ".join(bh) + "  " + "".join(bc)
    return out


def print_hex_diff(
    a_data, b_data, indent=0, num=16, out=print, show_same=False, base_addr=0
):
    na = len(a_data)
    nb = len(b_data)
    n = max(na, nb)
    o = 0
    addr = base_addr
    while o < n:
        a_line = a_data[o : o + num]
        b_line = b_data[o : o + num]
        if show_same or a_line != b_line:
            out(get_hex_diff_line(addr, a_line, b_line, indent, num))
        o += num
        addr += num


# mini test
if __name__ == "__main__":
    print_hex("hello, world!", num=8, base_addr=0xF80000)
    print_hex_diff("hello, world!", "hello. WOrld!", num=8, base_addr=0xF80000)
