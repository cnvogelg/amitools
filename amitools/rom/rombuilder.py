import os
import struct

from amitools.binfmt.Relocate import Relocate
from .kickrom import KickRomAccess


class RomEntryRaw:
    def __init__(self, name, data, relocs=None):
        self.name = name
        self.data = data
        self.relocs = relocs

    def get_size(self):
        return len(self.data)

    def get_data(self, addr):
        if self.relocs is None or len(self.relocs) == 0:
            return self.data
        else:
            data = bytearray(self.data)
            self._relocate(data, addr)
            return data

    def _relocate(self, data, addr):
        for pos in self.relocs:
            val = struct.unpack_from(">I", data, pos)
            val += addr
            struct.pack_into(">I", data, pos, val)


class RomEntryBinImg:
    def __init__(self, name, bin_img):
        self.name = name
        self.bin_img = bin_img
        self.relocator = Relocate(bin_img)

    def get_size(self):
        return self.relocator.get_total_size()

    def get_data(self, addr):
        return self.relocator.relocate_one_block(addr)


class RomEntryRomHdr:
    def __init__(self, name, skip, jmp_addr):
        self.name = name
        self.skip = skip
        self.jmp_addr = jmp_addr

    def get_size(self):
        return self.skip + 8

    def get_data(self, addr):
        data = chr(0xFF) * self.skip
        hdr = struct.pack(">II", 0x11114EF9, self.jmp_addr)
        return data + hdr


class RomEntryPadding:
    def __init__(self, skip, value=0):
        self.skip = skip
        self.value = value

    def get_size(self):
        return self.skip

    def get_data(self, addr):
        return chr(self.value) * self.skip


class RomBuilder:
    def __init__(self, size=512, base_addr=0xF80000, fill_byte=0xFF):
        self.size = size  # in KiB
        self.base_addr = base_addr
        self.fill_byte = fill_byte
        self.size_bytes = size * 1024
        # state
        self.modules = []
        self.rom_off = 0
        self.left_bytes = self.size_bytes
        self.data_off = 0
        self.error = None

    def get_error(self):
        return self.error

    def get_data_offset(self):
        return self.data_off

    def get_rom_offset(self):
        return self.rom_off + self.data_off

    def get_bytes_left(self):
        return self.left_bytes

    def does_fit(self, num_bytes):
        if num_bytes <= self.left_bytes:
            return True
        return False

    def _add_entry(self, entry):
        n = entry.get_size()
        if not self.does_fit(n):
            self.error = "module '%s' does not fit into ROM!" % (entry.name)
            return None
        # add entry
        self.modules.append(entry)
        self.data_off += n
        self.left_bytes -= n
        return entry

    def build_file_list(self, names):
        files = []
        for mod in names:
            # is an index file?
            if mod.endswith(".txt"):
                base_path = os.path.dirname(mod)
                with open(mod, "r") as fh:
                    for line in fh:
                        name = line.strip()
                        if len(name) > 0:
                            f = os.path.join(base_path, name)
                            files.append(f)
            else:
                files.append(mod)
        return files

    def add_module(self, name, data, relocs=None):
        e = RomEntryRaw(name, data, relocs)
        return self._add_entry(e)

    def add_bin_img(self, name, bin_img):
        e = RomEntryBinImg(name, bin_img)
        return self._add_entry(e)

    def add_padding(self, skip, value=0):
        e = RomEntryPadding(skip, value)
        return self._add_entry(e)

    def build_rom(self):
        rom_data = bytearray(self.size_bytes)
        # fill in modules
        addr = self.base_addr + self.rom_off
        off = self.rom_off
        for mod in self.modules:
            n = mod.get_size()
            rom_data[off : off + n] = mod.get_data(addr)
            off += n
            addr += n
        # fill empty space
        fill = self.fill_byte
        while off < self.size_bytes:
            rom_data[off] = fill
            off += 1
        return rom_data


class KickRomBuilder(RomBuilder):
    def __init__(self, size, kickety_split=True, rom_ver=None, **kw_args):
        RomBuilder.__init__(self, size, **kw_args)
        self.rom_ver = rom_ver
        # do we need a rom header at 256k border? (the original ROMs do this)
        if size == 512:
            self.kickety_split = kickety_split
            self.split_offset = 0x40000
        else:
            self.kickety_split = False
            self.split_offset = None
        # check size
        if size not in (256, 512):
            raise ValueError("KickROM size must be 256 or 512 KiB!")
        # we need a footer
        self.left_bytes -= KickRomAccess.FOOTER_SIZE
        # extra rom header takes 8
        if self.kickety_split:
            self.left_bytes -= KickRomAccess.ROMHDR_SIZE

    def cross_kickety_split(self, num_bytes):
        if self.kickety_split:
            new_off = self.data_off + num_bytes
            return self.data_off < self.split_offset and new_off > self.split_offset
        else:
            return False

    def add_kickety_split(self):
        jump_addr = self.base_addr + 2
        skip = self.split_offset - self.data_off
        e = RomEntryRomHdr("KicketySplit", skip, jump_addr)
        return self._add_entry(e)

    def build_rom(self):
        rom_data = RomBuilder.build_rom(self)
        # add kick sum
        kh = KickRomAccess(rom_data)
        # ensure that first module brought the header
        if not kh.check_header():
            self.error = "First KickROM module does not contain RomHdr!"
            return None
        # write custom rev?
        if self.rom_ver is not None:
            kh.write_rom_ver_rev(self.rom_ver)
        # write missing entries in footer
        kh.write_ext_footer()
        return rom_data


class ExtRomBuilder(RomBuilder):
    def __init__(
        self, size, rom_ver=None, add_footer=False, kick_addr=0xF80000, **kw_args
    ):
        RomBuilder.__init__(self, size, **kw_args)
        # kick addr for jump
        self.kick_addr = kick_addr
        # set ROM version
        if rom_ver is None:
            self.rom_ver = (45, 10)
        else:
            self.rom_ver = rom_ver
        # add footer
        self.add_footer = add_footer
        if add_footer:
            self.left_bytes -= KickRomAccess.FOOTER_SIZE
        # account for header
        self.left_bytes -= KickRomAccess.EXT_HEADER_SIZE
        self.rom_off = KickRomAccess.EXT_HEADER_SIZE

    def build_rom(self):
        rom_data = RomBuilder.build_rom(self)
        # write a header
        kh = KickRomAccess(rom_data)
        kh.write_ext_header(self.kick_addr + 2, self.rom_ver)
        # write footer
        if self.add_footer:
            kh.write_ext_footer()
        return rom_data
