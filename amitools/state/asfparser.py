from dataclasses import dataclass
from enum import IntEnum
import struct


class MemType(IntEnum):
    CHIP = 0
    BOGO = 1
    Z2RAM = 2
    Z3RAM = 3
    Z3CHIP = 4
    A3KLO = 5
    A3KHI = 6


@dataclass
class MemChunk:
    address: int
    size: int
    type: MemType
    data: bytes = None


@dataclass
class ExpansionRAM:
    z2ram_base: int
    z3ram_base: int
    gfx_base: int
    boro_base: int
    z2ram_base2: int


@dataclass
class ROMChunk:
    address: int
    size: int
    type: int
    version: int
    crc32: int
    name: str
    path: str
    data: bytes = None


class ASFParser:
    def __init__(self, asf_file):
        self.asf_file = asf_file

    def get_expansion_ram(self):
        data = self.asf_file.load_chunk("EXPA")
        if not data:
            return None
        assert len(data) >= 5 * 4
        z2b, z3b, gfx, boro, z2b2 = struct.unpack(">IIIII", data)
        return ExpansionRAM(z2b, z3b, gfx, boro, z2b2)

    def get_ram_layout(self, load_ram=False):
        layout = []
        # chip
        chip = self._get_mem_chunk("CRAM", MemType.CHIP, load_ram, 0)
        if chip:
            layout.append(chip)
        bogo = self._get_mem_chunk("BRAM", MemType.BOGO, load_ram, 0xC00000)
        # slow/bogo ram
        if bogo:
            layout.append(bogo)
        # a3k
        a3klo = self._get_mem_chunk("A3K1", MemType.A3KLO, load_ram, 0x08000000)
        if a3klo:
            # fixup lo address
            a3klo.address -= a3klo.size
            layout.append(a3klo)
        a3khi = self._get_mem_chunk("A3K2", MemType.A3KHI, load_ram, 0x08000000)
        if a3khi:
            layout.append(a3khi)
        # z2ram/z3ram
        expansion = self.get_expansion_ram()
        if expansion:
            # z2ram
            z2rams = self._get_all_mem_chunks("FRAM", MemType.Z2RAM, load_ram)
            n = len(z2rams)
            if n > 0:
                z2ram = z2rams[0]
                z2ram.address = expansion.z2ram_base
                layout.append(z2ram)
            if n > 1:
                z2ram = z2rams[1]
                z2ram.address = expansion.z2ram_base2
                layout.append(z2ram)
            assert n < 3
            # z2ram
            z3rams = self._get_all_mem_chunks("ZRAM", MemType.Z3RAM, load_ram)
            n = len(z3rams)
            if n > 0:
                z3ram = z3rams[0]
                z3ram.address = expansion.z3ram_base
                layout.append(z3ram)
            assert n < 2
        return layout

    def get_roms(self):
        datas = self.asf_file.load_all_chunks("ROM ")
        if datas:
            return list(map(lambda x: self._parse_rom(x), datas))

    def _parse_rom(self, data):
        addr, size, type, ver, crc = struct.unpack_from(">IIIII", data)
        offset = 5 * 4
        name, offset = self.asf_file._read_string(data, offset)
        path, offset = self.asf_file._read_string(data, offset)
        chunk = ROMChunk(addr, size, type, ver, crc, name, path)

        # hack for missing start addr
        if chunk.address == 0 and chunk.type == 1:
            chunk.address = 0xF00000

        # in place ROM?
        if len(data) > offset:
            chunk.data = data[offset:]
        return chunk

    def _get_all_mem_chunks(self, tag, type, load_ram):
        result = []
        if load_ram:
            datas = self.asf_file.load_all_chunks(tag)
            if datas:
                for data in datas:
                    size = len(data)
                    result.append(MemChunk(0, size, type, data))
        else:
            chunks = self.asf_file.get_all_chunks(tag)
            if chunks:
                for chunk in chunks:
                    size = chunk.uncompressed_size
                    result.append(MemChunk(0, size, type))
        return result

    def _get_mem_chunk(self, tag, type, load_ram, addr=0):
        if load_ram:
            data = self.asf_file.load_chunk(tag)
            if not data:
                return None
            size = len(data)
        else:
            data = None
            chunk = self.asf_file.get_chunk(tag)
            if not chunk:
                return None
            size = chunk.uncompressed_size
        return MemChunk(addr, size, type, data)
