from .FSError import *


class ProtectFlags:
    FIBF_DELETE = 1
    FIBF_EXECUTE = 2
    FIBF_WRITE = 4
    FIBF_READ = 8
    FIBF_ARCHIVE = 16
    FIBF_PURE = 32
    FIBF_SCRIPT = 64

    flag_txt = "HSPArwed"
    flag_num = len(flag_txt)
    flag_none = 0xF  # --------
    empty_string = "-" * flag_num

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
        m = 1 << (self.flag_num - 1)
        for i in range(self.flag_num):
            if m & self.mask == m:
                res += "1"
            else:
                res += "0"
            m >>= 1
        return res

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
        n = self.flag_txt
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
                if mask == None:
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
        if not i in s:
            print(s)
