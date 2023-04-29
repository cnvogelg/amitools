"""work on a Kickstart ROM"""

import os
import struct
import logging

from .romaccess import RomAccess


class KickRomAccess(RomAccess):
    """Access a kickstart ROM"""

    EXT_HEADER_SIZE = 0x10
    FOOTER_SIZE = 0x18
    ROMHDR_SIZE = 8
    ROMHDR_256K = 0x11114EF9
    ROMHDR_512K = 0x11144EF9
    ROMHDR_EXT = 0x11144EF9

    def __init__(self, rom_data):
        RomAccess.__init__(self, rom_data)

    def is_kick_rom(self):
        """Check if given ROM is a Kickstart ROM"""
        return self.detect_kick_rom() == "ok"

    def detect_kick_rom(self):
        """ROM detection returns "ok" or error string"""
        if not self.check_size():
            return "size check failed"
        if not self.check_header():
            return "header check failed"
        if not self.check_footer():
            return "footer check failed"
        if not self.check_rom_size_field():
            return "rom size field mismatch"
        if not self.verify_check_sum():
            return "check sum mismatch"
        return "ok"

    def check_header(self):
        # expect 0x1114 0x4ef9
        val = self.read_long(0)
        logging.debug("Header %08x" % val, self.kib)
        if self.kib == 512:
            return val == self.ROMHDR_512K
        elif self.kib == 256:
            # Extended roms also have 0x11144ef9
            return (val == self.ROMHDR_256K) or (val == self.ROMHDR_EXT)
        elif self.kib == 1536 or self.kib == 3584:
            # Extended roms also have 0x11144ef9
            return val == self.ROMHDR_EXT
        else:
            return False

    def check_kickety_split(self):
        # expect 0x1111 0x4ef9
        if self.kib == 512:
            val = self.read_long(0x40000)
            return val == self.ROMHDR_256K
        else:
            return False

    def check_footer(self):
        # expect 0x0019 ... 0x001f
        off = self.size - 14
        num = 0x19
        for i in range(7):
            val = self.read_word(off)
            if val != num:
                return False
            num += 1
            off += 2
        return True

    def check_size(self):
        # expect 256k or 512k ROM
        if self.size % 1024 != 0:
            return False
        if self.kib not in (256, 512):
            return False
        return True

    def check_rom_size_field(self):
        return self.read_rom_size_field() == self.size

    def check_magic_reset(self):
        return self.read_word(0xD0) == 0x4E70

    def calc_check_sum(self, skip_off=None):
        """Check internal kickstart checksum and return True if is correct"""
        chk_sum = 0
        num_longs = self.size // 4
        off = 0
        max_u32 = 0xFFFFFFFF
        for i in range(num_longs):
            val = struct.unpack_from(">I", self.rom_data, off)[0]
            if off != skip_off:
                chk_sum += val
            off += 4
            if chk_sum > max_u32:
                chk_sum = chk_sum & max_u32
                chk_sum += 1
        return max_u32 - chk_sum

    def verify_check_sum(self):
        chk_sum = self.calc_check_sum()
        return chk_sum == 0

    def read_check_sum(self):
        sum_off = self.size - 0x18
        return self.read_long(sum_off)

    def recalc_check_sum(self):
        sum_off = self.size - 0x18
        return self.calc_check_sum(sum_off)

    def write_check_sum(self):
        cs = self.recalc_check_sum()
        sum_off = self.size - 0x18
        self.write_long(sum_off, cs)
        return cs

    def write_rom_size_field(self):
        off = self.size - 0x14
        self.write_long(off, self.size)

    def write_header(self, jump_addr, kickety_split=False):
        if kickety_split:
            offset = 0x40000
            hdr = self.ROMHDR_256K
        elif self.kib == 256:
            offset = 0
            hdr = self.ROMHDR_256K
        else:
            offset = 0
            hdr = self.ROMHDR_512K
        self.write_long(offset, hdr)
        self.write_long(offset + 4, jump_addr)

    def write_ext_header(self, jump_addr, rom_rev):
        self.write_header(jump_addr)
        self.write_word(8, 0)
        self.write_word(10, 0xFFFF)
        self.write_word(12, rom_rev[0])
        self.write_word(14, rom_rev[1])

    def write_ext_footer(self):
        self.write_footer()
        self.write_rom_size_field()
        self.write_check_sum()

    def write_footer(self):
        off = self.size - 0x10
        num = 0x18
        for i in range(8):
            self.write_word(off, num)
            num += 1
            off += 2

    def write_rom_ver_rev(self, rom_rev):
        """get (ver, rev) version info from ROM"""
        return struct.pack_into(">HH", self.rom_data, 12, rom_rev[0], rom_rev[1])

    def read_boot_pc(self):
        """return PC for booting the ROM"""
        return self.read_long(4)

    def read_rom_ver_rev(self):
        """get (ver, rev) version info from ROM"""
        return struct.unpack_from(">HH", self.rom_data, 12)

    def read_exec_ver_rev(self):
        """get (ver, rev) version info from ROM"""
        return struct.unpack_from(">HH", self.rom_data, 16)

    def read_rom_size_field(self):
        """return size of ROM stored in ROM itself"""
        off = self.size - 0x14
        return self.read_long(off)

    def get_base_addr(self):
        return self.read_boot_pc() & ~0xFFFF


class Loader(object):
    """Load kick rom images in different formats"""

    @classmethod
    def load(cls, kick_file, rom_key_file=None):
        raw_img = None
        rom_key = None
        # read rom image
        with open(kick_file, "rb") as fh:
            raw_img = fh.read()
        # coded rom?
        need_key = False
        if raw_img[:11] == b"AMIROMTYPE1":
            rom_img = raw_img[11:]
            need_key = True
        else:
            rom_img = raw_img
        # decode rom
        if need_key:
            # read key file
            if rom_key_file is None:
                path = os.path.dirname(kick_file)
                rom_key_file = os.path.join(path, "rom.key")
            with open(rom_key_file, "rb") as fh:
                rom_key = fh.read()
            rom_img = cls._decode(rom_img, rom_key)
        return rom_img

    @classmethod
    def _decode(cls, img, rom_key):
        data = bytearray(img)
        n = len(rom_key)
        for i in range(len(data)):
            off = i % n
            data[i] = data[i] ^ rom_key[off]
        return bytes(data)


# tiny test
if __name__ == "__main__":
    import sys

    args = sys.argv
    n = len(args)
    if n > 1:
        ks_file = args[1]
    else:
        ks_file = "amiga-os-310-a500.rom"
    print(ks_file)
    ks = Loader.load(ks_file, "rom.key")
    kh = KickRomAccess(ks)
    print("is_kick_rom", kh.is_kick_rom())
    print("detect_kick_rom", kh.detect_kick_rom())
    print("pc=%08x" % kh.read_boot_pc())
    print("ver,rev=", kh.read_rom_ver_rev())
    print("ver,rev=", kh.read_exec_ver_rev())
    print("size %08x == %08x" % (kh.read_rom_size_field(), len(ks)))
    print("base %08x" % kh.get_base_addr())
    print("get chk_sum=%08x" % kh.read_check_sum())
    print("calc chk_sum=%08x" % kh.recalc_check_sum())
    with open("out.rom", "wb") as fh:
        fh.write(ks.get_data())
