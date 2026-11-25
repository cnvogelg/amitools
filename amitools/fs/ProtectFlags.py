from .FSError import FSError, INVALID_PROTECT_FORMAT


class ProtectFlags:
    # owner bits (active low)
    FIBF_DELETE = 1
    FIBF_EXECUTE = 2
    FIBF_WRITE = 4
    FIBF_READ = 8
    FIBF_ARCHIVE = 16
    FIBF_PURE = 32
    FIBF_SCRIPT = 64
    FIBF_HOLD = 128
    # group bits (active high)
    FIBF_GRP_DELETE = 1 << 8
    FIBF_GRP_EXECUTE = 1 << 9
    FIBF_GRP_WRITE = 1 << 10
    FIBF_GRP_READ = 1 << 11
    # other bits (active high)
    FIBF_OTR_DELETE = 1 << 12
    FIBF_OTR_EXECUTE = 1 << 13
    FIBF_OTR_WRITE = 1 << 14
    FIBF_OTR_READ = 1 << 15
    # set user id (bit 31)
    FIBF_SUID = 1 << 31

    flag_txt = "HSPArwed"
    flag_num = len(flag_txt)
    flag_none = 0xF  # --------
    empty_string = "-" * flag_num

    # number of bits in the whole protection long
    mask_num = 32
    # the bits the 8-char owner string cannot show: group, other and SUID
    extra_bits = (
        FIBF_GRP_DELETE
        | FIBF_GRP_EXECUTE
        | FIBF_GRP_WRITE
        | FIBF_GRP_READ
        | FIBF_OTR_DELETE
        | FIBF_OTR_EXECUTE
        | FIBF_OTR_WRITE
        | FIBF_OTR_READ
        | FIBF_SUID
    )

    def __init__(self, mask=0):
        self.mask = mask

    def get_mask(self):
        return self.mask

    def __str__(self):
        txt = ""
        pos = self.flag_num - 1
        m = 1 << pos
        for i in range(self.flag_num):
            bit = self.mask & m == m
            show = "-"
            flg = self.flag_txt[i]
            flg_low = flg.lower()
            if bit:
                if flg_low != flg:
                    show = flg_low
            else:
                if flg_low == flg:
                    show = flg_low
            txt += show
            m >>= 1
            pos -= 1
        return txt

    def bin_str(self):
        res = ""
        m = 1 << (self.mask_num - 1)
        for i in range(self.mask_num):
            if m & self.mask == m:
                res += "1"
            else:
                res += "0"
            m >>= 1
        return res

    def has_extra(self):
        """whether group/other/SUID bits are set beyond the 8-char owner form"""
        return self.mask & self.extra_bits != 0

    def extra_str(self):
        """hex form of the full protection long, e.g. ``0x0000800f``"""
        return "0x%08x" % self.mask

    def short_str(self):
        return str(self).replace("-", "")

    def parse_full(self, s):
        """parse a string with all flags"""
        n = len(self.flag_txt)
        if len(s) != n:
            raise ValueError("full string size mismatch!")
        mask = 0
        for i in range(n):
            val = s[i]
            ref = self.flag_txt[i]
            ref_lo = ref.lower()
            if val not in (ref, ref_lo, "-"):
                raise ValueError("invalid protect char: " + val)
            is_lo = ref == ref_lo
            is_blank = val == "-"
            if is_lo:
                do_set = is_blank
            else:
                do_set = not is_blank
            if do_set:
                bit_pos = n - i - 1
                bit_mask = 1 << bit_pos
                mask |= bit_mask
        self.mask = mask

    def parse(self, s):
        if len(s) == 0:
            return
        # allow to add with '+' or sub with '-'
        mode = "+"
        self.mask = self.flag_none
        for a in s.lower():
            if a in "+-":
                mode = a
            else:
                mask = None
                is_low = None
                for i in range(self.flag_num):
                    flg = self.flag_txt[i]
                    flg_low = flg.lower()
                    if flg_low == a:
                        mask = 1 << (self.flag_num - 1 - i)
                        is_low = flg_low == flg
                        break
                if mask is None:
                    raise FSError(INVALID_PROTECT_FORMAT, extra="char: " + a)
                # apply mask
                if mode == "+":
                    if is_low:
                        self.mask &= ~mask
                    else:
                        self.mask |= mask
                else:
                    if is_low:
                        self.mask |= mask
                    else:
                        self.mask &= ~mask

    def is_set(self, mask):
        return self.mask & mask == 0  # LO active

    def set(self, mask):
        self.mask &= ~mask

    def clr(self, mask):
        self.mask |= mask

    def is_d(self):
        return self.is_set(self.FIBF_DELETE)

    def is_e(self):
        return self.is_set(self.FIBF_EXECUTE)

    def is_w(self):
        return self.is_set(self.FIBF_WRITE)

    def is_r(self):
        return self.is_set(self.FIBF_READ)


if __name__ == "__main__":
    inp = ["h", "s", "p", "a", "r", "w", "e", "d"]
    for i in inp:
        p = ProtectFlags()
        p.parse(i)
        s = str(p)
        if i not in s:
            print(s)
