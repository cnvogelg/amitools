import os
import struct


class RemusRom(object):
    def __init__(self, sum_off, chk_sum, size, base_addr, name, short_name, flags):
        self.sum_off = sum_off
        self.chk_sum = chk_sum
        self.size = size
        self.base_addr = base_addr
        self.name = name
        self.short_name = short_name
        self.flags = flags
        self.modules = []

    def __repr__(self):
        return (
            "RemusRom(sum_off=%08x,chk_sum=%08x,size=%08x,base_addr=%08x,"
            "name=%s,short_name=%s,flags=%x)"
            % (
                self.sum_off,
                self.chk_sum,
                self.size,
                self.base_addr,
                self.name,
                self.short_name,
                self.flags,
            )
        )

    def dump(self):
        print(
            "(%04x) #%04x  @%08x  +%08x  =%08x  %08x: %08x  %-24s  %s"
            % (
                self.flags,
                len(self.modules),
                self.base_addr,
                self.size,
                self.base_addr + self.size,
                self.sum_off,
                self.chk_sum,
                self.short_name,
                self.name,
            )
        )
        for m in self.modules:
            m.dump()


class RemusRomModuleExtra(object):
    def __init__(self, flags, relocs, patches, chk_sum, brelocs, fixes):
        self.flags = flags
        self.relocs = relocs
        self.patches = patches
        self.chk_sum = chk_sum
        self.brelocs = brelocs
        self.fixes = fixes

    def __repr__(self):
        return (
            "RemusRomModuleExtra(relocs=%r,patches=%r,chk_sum=%08x,"
            "brelocs=%r,fixes=%r)"
            % (self.relocs, self.patches, self.chk_sum, self.brelocs, self.fixes)
        )

    def dump(self):
        if len(self.relocs) > 0:
            print("    relocs: ", ",".join(["%08x" % x for x in self.relocs]))
        if len(self.patches) > 0:
            print("    patches:", ",".join(["%08x:%08x" % x for x in self.patches]))
        if len(self.brelocs) > 0:
            print("    brelocs:", ",".join(["%08x" % x for x in self.brelocs]))
        if len(self.fixes) > 0:
            print("    fixes:  ", ",".join(["%08x:%08x" % x for x in self.fixes]))
        if self.chk_sum:
            print("    chk_sum: %08x" % self.chk_sum)


class RemusRomModule(object):
    def __init__(self, name, offset, size, extra_off):
        self.name = name
        self.offset = offset
        self.size = size
        self.extra_off = extra_off
        self.extra = None

    def __repr__(self):
        return "RemusRomModule(name=%s,offset=%08x,size=%08x,extra_off=%08x)" % (
            self.name,
            self.offset,
            self.size,
            self.extra_off,
        )

    def dump(self):
        if self.extra:
            flags = self.extra.flags
        else:
            flags = 0
        print(
            "  @%08x  +%08x  =%08x  %s  (%02x)"
            % (self.offset, self.size, self.offset + self.size, self.name, flags)
        )
        if self.extra:
            self.extra.dump()


class RemusFile(object):
    def __init__(self, header):
        self.data = None
        self.offset = 0
        self.header = header
        self.version = None

    def load(self, path):
        with open(path, "rb") as fh:
            self.data = fh.read()
        self.offset = 0
        # check header
        len_hdr = self._read_long()
        if len_hdr != self.header:
            raise IOError("Wrong header! %08x != %08x" % (self.header, len_hdr))
        # read version
        self.version = self._read_long()
        self.path = path

    def get_version(self):
        return self.version

    def _read_long(self, offset=None):
        if offset is None:
            offset = self.offset
            self.offset += 4
        return struct.unpack_from(">I", self.data, offset)[0]

    def _read_word(self, offset=None):
        if offset is None:
            offset = self.offset
            self.offset += 2
        return struct.unpack_from(">H", self.data, offset)[0]

    def _read_string(self, pos):
        res = []
        while True:
            if self.data[pos] == 0:
                break
            res.append(self.data[pos])
            pos += 1
        return bytes(res).decode("latin-1")


class RemusSplitFile(RemusFile):
    u32_max = 0xFFFFFFFF

    def __init__(self):
        RemusFile.__init__(self, 0x524D5346)
        self.roms = []

    def load(self, path):
        RemusFile.load(self, path)
        # currently supported versions:
        assert self.version in (0x20005, 0x20007)
        self.roms = []
        extra_offs = set()
        string_offs = set()
        # loop roms
        while self._read_rom(extra_offs, string_offs):
            pass
        # find min string off -> end offset for extras
        end_off = self.u32_max
        for str_off in string_offs:
            if str_off < end_off:
                end_off = str_off
        # read module extras
        extra_map = self._read_extras(extra_offs, end_off)
        # assign extras to modules
        self._assign_module_extras(extra_map)

    def _read_rom(self, extra_offs, string_offs):
        num_modules = self._read_long()
        if num_modules == self.u32_max:
            return False
        sum_off = self._read_long()
        chk_sum = self._read_long()
        size = self._read_long()
        name_off = self._read_long()
        base_addr = self._read_long()
        short_name_off = self._read_long()
        if self.version > 0x20005:
            flags = self._read_long()
        else:
            flags = 0
        name = self._read_string(name_off)
        short_name = self._read_string(short_name_off)
        rom = RemusRom(sum_off, chk_sum, size, base_addr, name, short_name, flags)
        # store
        string_offs.add(name_off)
        string_offs.add(short_name_off)
        self.roms.append(rom)
        # now parse modules for this rom
        while self._read_module(rom, extra_offs, string_offs):
            pass
        assert len(rom.modules) == num_modules
        # sort modules by offset
        rom.modules.sort(key=lambda x: x.offset)
        return True

    def _read_module(self, rom, extra_offs, string_offs):
        name_off = self._read_long()
        if name_off == self.u32_max:
            return False
        offset = self._read_long()
        size = self._read_long()
        extra_off = self._read_long()
        name = self._read_string(name_off)
        entry = RemusRomModule(name, offset, size, extra_off)
        # store
        extra_offs.add(extra_off)
        string_offs.add(name_off)
        rom.modules.append(entry)
        return True

    def _read_extras(self, extra_offs, end_off):
        FLAG_SHORT_RELOCS = 0x01
        FLAG_LONG_RELOCS = 0x02
        FLAG_SHORT_PATCHES = 0x04
        FLAG_LONG_PATCHES = 0x08
        FLAG_SHORT_BCPL_RELOCS = 0x10
        FLAG_CHK_SUM = 0x40
        FLAG_FIXES = 0x80
        FLAG_MASK = 0xDF
        # parse extras
        extra_map = {}
        for extra_off in extra_offs:
            # set read offset
            self.offset = extra_off

            relocs = []
            patches = []
            brelocs = []
            fixes = []
            chk_sum = 0

            # read contents flag
            flags = self._read_word()
            assert flags & ~FLAG_MASK == 0

            # short patch
            if flags & FLAG_SHORT_PATCHES:
                num = self._read_word()
                for i in range(num):
                    offset = self._read_word()
                    val = self._read_long()
                    patches.append((offset, val))
            # long patch
            if flags & FLAG_LONG_PATCHES:
                num_patches = self._read_word()
                for i in range(num_patches):
                    offset = self._read_long()
                    val = self._read_long()
                    patches.append((offset, val))
            # short relocs
            if flags & FLAG_SHORT_RELOCS:
                num_short_relocs = self._read_word()
                for i in range(num_short_relocs):
                    off = self._read_word()
                    relocs.append(off)
            # long relocs
            if flags & FLAG_LONG_RELOCS:
                num_long_relocs = self._read_word()
                for i in range(num_long_relocs):
                    off = self._read_long()
                    relocs.append(off)
            # old dos.library BCPL relocs
            if flags & FLAG_SHORT_BCPL_RELOCS:
                num = self._read_word()
                for i in range(num):
                    off = self._read_word()
                    brelocs.append(off)
            # fixes
            if flags & FLAG_FIXES:
                num = self._read_word()
                for i in range(num):
                    off = self._read_long()
                    val = self._read_long()
                    fixes.append((off, val))
            # chk sum
            if flags & FLAG_CHK_SUM:
                chk_sum = self._read_long()
            # create extra
            e = RemusRomModuleExtra(flags, relocs, patches, chk_sum, brelocs, fixes)
            extra_map[extra_off] = e
            # check end of record
            # if self.offset not in extra_offs and self.offset != end_off:
            #  print("EOR  %s: %08x, %08x, %08x" % (self.path, extra_off,
            #        self.offset, end_off))
        return extra_map

    def _assign_module_extras(self, extra_map):
        for rom in self.roms:
            for module in rom.modules:
                module.extra = extra_map[module.extra_off]

    def dump(self):
        for rom in self.roms:
            rom.dump()

    def find_rom(self, rom_data, chk_sum):
        rom_size = len(rom_data)
        for rom in self.roms:
            # ok. size and checksum do match!
            if rom_size == rom.size and chk_sum == rom.chk_sum:
                return rom

    def get_roms(self, roms):
        roms += self.roms


class RemusIdEntry(object):
    def __init__(self, count, bogus, chk_sum, name):
        self.count = count
        self.bogus = bogus
        self.chk_sum = chk_sum
        self.name = name

    def __repr__(self):
        return "RemusIdEntry(count=%x,bogus=%08x,chk_sum=%08x,name=%s" % (
            self.count,
            self.bogus,
            self.chk_sum,
            self.name,
        )


class RemusIdFile(RemusFile):
    def __init__(self):
        RemusFile.__init__(self, 0x524D4944)
        self.entries = []

    def load(self, path):
        RemusFile.load(self, path)
        u16_max = 0xFFFF
        # loop: new rom
        while True:
            # parse rom entry
            count = self._read_word()
            if count == u16_max:
                break
            bogus = self._read_long()
            chk_sum = self._read_long()
            name_off = self._read_long()
            name = self._read_string(name_off)
            entry = RemusIdEntry(count, bogus, chk_sum, name)
            self.entries.append(entry)

    def dump(self):
        for e in self.entries:
            print("%04x  %08x  %08x  %s" % (e.count, e.bogus, e.chk_sum, e.name))


class RemusFileSet(object):
    def __init__(self):
        self.split_files = []
        self.id_file = None

    def load(self, data_dir):
        # id file?
        id_file = os.path.join(data_dir, "romid.idat")
        if os.path.exists(id_file):
            si = RemusIdFile()
            si.load(id_file)
            self.id_file = si
        # load *.dat files
        for f in os.listdir(data_dir):
            file = os.path.join(data_dir, f)
            if file.endswith(".dat"):
                sf = RemusSplitFile()
                sf.load(file)
                self.split_files.append(sf)

    def dump(self):
        for sf in self.split_files:
            sf.dump()
        if self.id_file is not None:
            self.id_file.dump()

    def find_rom(self, rom_data, chk_sum):
        for f in self.split_files:
            rom = f.find_rom(rom_data, chk_sum)
            if rom is not None:
                return rom

    def get_roms(self):
        roms = []
        for f in self.split_files:
            f.get_roms(roms)
        roms = sorted(roms, key=lambda x: x.name)
        return roms


if __name__ == "__main__":
    import sys
    from .kickrom import Loader, KickRomAccess

    if len(sys.argv) > 0:
        for f in sys.argv[1:]:
            sf = RemusSplitFile()
            sf.load(f)
            sf.dump()
    else:
        rfs = RemusFileSet()
        rfs.load("../data/splitdata")
        rfs.dump()
        if sys.argv:
            for rom_path in sys.argv[1:]:
                rom_img = Loader.load(rom_path)
                kh = KickRomAccess(rom_img)
                if kh.is_kick_rom():
                    chk_sum = kh.read_check_sum()
                else:
                    chk_sum = kh.calc_check_sum()
                found_rom = rfs.find_rom(rom_img, chk_sum)
                print(found_rom)
