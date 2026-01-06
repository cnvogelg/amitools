import stat

# Fallbacks for Windows (these map to HOLD, PURE, SCRIPT)
_S_ISUID = getattr(stat, "S_ISUID", 0)
_S_ISGID = getattr(stat, "S_ISGID", 0)
_S_ISVTX = getattr(stat, "S_ISVTX", 0)


class DosProtection:
    # Base owner bits (active low: 1 = disabled)
    FIBF_DELETE = 1
    FIBF_EXECUTE = 2
    FIBF_WRITE = 4
    FIBF_READ = 8

    # Special bits (active high: 1 = enabled)
    FIBF_ARCHIVE = 16
    FIBF_PURE = 32
    FIBF_SCRIPT = 64
    FIBF_HOLD = 128

    # Group bits (active high: 1 = enabled)
    FIBF_GRP_DELETE = 1 << 8
    FIBF_GRP_EXECUTE = 1 << 9
    FIBF_GRP_WRITE = 1 << 10
    FIBF_GRP_READ = 1 << 11

    # Other bits (active high: 1 = enabled)
    FIBF_OTR_DELETE = 1 << 12
    FIBF_OTR_EXECUTE = 1 << 13
    FIBF_OTR_WRITE = 1 << 14
    FIBF_OTR_READ = 1 << 15

    flag_txt = "sparwed"

    def __init__(self, mask):
        self.mask = mask

    def __str__(self):
        txt = "[%02x]" % self.mask
        val = 64
        for i in range(7):
            if self.mask & val == val:
                txt += "-"
            else:
                txt += self.flag_txt[i]
            val >>= 1
        return txt

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

    @classmethod
    def from_host_mode(cls, mode):
        """Convert host (Unix/POSIX) file mode to Amiga protection mask.

        Owner R/W/E/D bits are active low (1 = disabled).
        Group/Other and special bits are active high (1 = enabled).
        """
        # Owner bits: inverted (Unix bit set = Amiga bit clear)
        prot = (
            (0 if mode & stat.S_IRUSR else cls.FIBF_READ)
            | (0 if mode & stat.S_IWUSR else cls.FIBF_WRITE | cls.FIBF_DELETE)
            | (0 if mode & stat.S_IXUSR else cls.FIBF_EXECUTE)
            |
            # Group bits: direct mapping
            (cls.FIBF_GRP_READ if mode & stat.S_IRGRP else 0)
            | (cls.FIBF_GRP_WRITE | cls.FIBF_GRP_DELETE if mode & stat.S_IWGRP else 0)
            | (cls.FIBF_GRP_EXECUTE if mode & stat.S_IXGRP else 0)
            |
            # Other bits: direct mapping
            (cls.FIBF_OTR_READ if mode & stat.S_IROTH else 0)
            | (cls.FIBF_OTR_WRITE | cls.FIBF_OTR_DELETE if mode & stat.S_IWOTH else 0)
            | (cls.FIBF_OTR_EXECUTE if mode & stat.S_IXOTH else 0)
            |
            # Special bits: SUID -> HOLD, SGID -> PURE, sticky -> SCRIPT
            (cls.FIBF_HOLD if mode & _S_ISUID else 0)
            | (cls.FIBF_PURE if mode & _S_ISGID else 0)
            | (cls.FIBF_SCRIPT if mode & _S_ISVTX else 0)
        )
        return cls(prot)

    def to_host_mode(self):
        """Convert Amiga protection mask to host (Unix/POSIX) file mode.

        Owner R/W/E/D bits are active low (1 = disabled).
        Group/Other and special bits are active high (1 = enabled).
        """
        m = self.mask
        # Owner bits: inverted (Amiga bit set = Unix bit clear)
        mode = (
            (0 if m & self.FIBF_READ else stat.S_IRUSR)
            | (0 if m & self.FIBF_WRITE else stat.S_IWUSR)
            | (0 if m & self.FIBF_EXECUTE else stat.S_IXUSR)
            |
            # Group bits: direct mapping
            (stat.S_IRGRP if m & self.FIBF_GRP_READ else 0)
            | (stat.S_IWGRP if m & self.FIBF_GRP_WRITE else 0)
            | (stat.S_IXGRP if m & self.FIBF_GRP_EXECUTE else 0)
            |
            # Other bits: direct mapping
            (stat.S_IROTH if m & self.FIBF_OTR_READ else 0)
            | (stat.S_IWOTH if m & self.FIBF_OTR_WRITE else 0)
            | (stat.S_IXOTH if m & self.FIBF_OTR_EXECUTE else 0)
            |
            # Special bits: HOLD -> SUID, PURE -> SGID, SCRIPT -> sticky
            (_S_ISUID if m & self.FIBF_HOLD else 0)
            | (_S_ISGID if m & self.FIBF_PURE else 0)
            | (_S_ISVTX if m & self.FIBF_SCRIPT else 0)
        )
        return mode
