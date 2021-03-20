import fnmatch
import struct

from . import kickrom
from . import remusfile
import amitools.util.DataDir as DataDir
from amitools.binfmt.BinImage import (
    BinImage,
    Segment,
    Relocations,
    Reloc,
    BIN_IMAGE_TYPE_HUNK,
    SEGMENT_TYPE_CODE,
)


class RomSplitter:
    def __init__(self, split_data_path=None):
        # get data file path
        if split_data_path is None:
            split_data_path = DataDir.ensure_data_sub_dir("splitdata")
        # setup remus file set
        self.rfs = remusfile.RemusFileSet()
        self.rfs.load(split_data_path)
        # state
        self.chk_sum = None
        self.rom_data = None
        self.remus_rom = None

    def list_roms(self, out, query=None, show_entries=False):
        roms = self.rfs.get_roms()
        for rom in roms:
            if query is None or fnmatch.fnmatch(rom.name, query):
                self.remus_rom = rom
                self.print_rom(out, show_entries)

    def find_rom(self, rom_path):
        """load ROM and try to find a matching dat file.
        Returns True if ROM was matched"""
        self.rom_data = kickrom.Loader.load(rom_path)
        # get check sum
        kh = kickrom.KickRomAccess(self.rom_data)
        if kh.is_kick_rom():
            self.chk_sum = kh.read_check_sum()
        else:
            self.chk_sum = kh.calc_check_sum()
        # search rom in Remus data base
        self.remus_rom = self.rfs.find_rom(self.rom_data, self.chk_sum)
        return self.remus_rom

    def print_rom(self, out, show_entries=False):
        rom = self.remus_rom
        out(
            "rom @%06x  +%06x  sum=%08x@%08x  %s"
            % (rom.base_addr, rom.size, rom.chk_sum, rom.sum_off, rom.name)
        )
        if show_entries:
            for module in rom.modules:
                self.print_entry(out, module)

    def print_entry(self, out, entry):
        out(
            "    @%06x  +%06x  =%06x  (r:%5d,f:%2d,p:%2d)  sum=%08x  %s"
            % (
                entry.offset,
                entry.size,
                entry.offset + entry.size,
                len(entry.extra.relocs),
                len(entry.extra.fixes),
                len(entry.extra.patches),
                entry.extra.chk_sum,
                entry.name,
            )
        )

    def print_entries(self, out, entries):
        for e in entries:
            self.print_entry(out, e)

    def get_all_entries(self):
        return self.remus_rom.modules

    def query_entries(self, query_str):
        res = []
        for e in self.remus_rom.modules:
            if fnmatch.fnmatch(e.name, query_str):
                res.append(e)
        return res

    def extract_entry(self, entry, fixes=True, patches=False):
        """return data, relocs"""
        data = self.rom_data[entry.offset : entry.offset + entry.size]
        extra = entry.extra
        relocs = extra.relocs
        entry_addr = self.remus_rom.base_addr + entry.offset
        data = self._clean_relocs(data, relocs, entry_addr)
        if fixes and len(extra.fixes) > 0:
            self._apply_patches(data, extra.fixes)
        if patches and len(extra.patches) > 0:
            self._apply_patches(data, extra.patches)
        return data, relocs

    def _apply_patches(self, data, patches):
        for off, val in patches:
            struct.pack_into(">I", data, off, val)

    def _clean_relocs(self, data, relocs, base_addr):
        if type(data) is not bytearray:
            data = bytearray(data)
        for off in relocs:
            addr = struct.unpack_from(">I", data, off)[0]
            if addr < base_addr:
                raise ValueError(
                    "Invalid relocatable address: %08x base=%08x" % (addr, base_addr)
                )
            addr -= base_addr
            struct.pack_into(">I", data, off, addr)
        return data

    def extract_bin_img(self, entry, fixes=True, patches=False):
        data, relocs = self.extract_entry(entry, fixes, patches)
        # create a bin image
        bi = BinImage(BIN_IMAGE_TYPE_HUNK)
        seg = Segment(SEGMENT_TYPE_CODE, len(data), data)
        bi.add_segment(seg)
        # create reloc for target segment
        if relocs:
            rl = Relocations(seg)
            # add offsets
            for o in relocs:
                r = Reloc(o)
                rl.add_reloc(r)
            seg.add_reloc(seg, rl)
        # return final binary image
        return bi

    def write_index_file(self, idx_path):
        with open(idx_path, "w") as fh:
            for e in self.remus_rom.modules:
                fh.write(e.name + "\n")
