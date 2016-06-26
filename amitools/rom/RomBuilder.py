import struct

from amitools.binfmt.BinImage import *
from amitools.binfmt.Relocate import *
import KickRom


class RomEntryRaw:
  def __init__(self, name, data, relocs):
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
    data = chr(0xff) * self.skip
    hdr = struct.pack(">II", 0x11114ef9, self.jmp_addr)
    return data + hdr


class RomBuilder:
  def __init__(self, size=512, base_addr=0xf8000, fill_byte=0xff,
               chunk_size=256, kick_sum=True):
    if chunk_size == 0:
      chunk_size = size
    self.size = size # in KiB
    self.base_addr = base_addr
    self.fill_byte = fill_byte
    self.chunk_size = chunk_size
    self.kick_sum = kick_sum
    self.size_bytes = size * 1024
    self.chunk_size_bytes = chunk_size * 1024
    # state
    self.modules = []
    self.cur_off = 0
    self.cur_chunk = 0
    self.error = None

  def get_current_offset(self):
    return self.cur_off

  def get_bytes_left(self):
    return self.size_bytes - self.cur_off

  def does_fit(self, num_bytes):
    off = self.cur_off % self.chunk_size_bytes
    # fits into current chunk
    if num_bytes + off <= self.chunk_size_bytes:
      return True
    # move to next chunk
    off += self.chunk_size_bytes - self.cur_chunk + 8
    if num_bytes + off <= self.size_bytes:
      return True
    return False

  def _add_entry(self, entry):
    n = entry.get_size()
    if not self.does_fit(n):
      self.error = "module '%s' does not fit into ROM!" % (entry.name)
      return None
    # add rom header
    if (self.cur_chunk + n) > self.chunk_size_bytes:
      skip = self.chunk_size_bytes - self.cur_chunk
      self.cur_off += skip + 8
      self.cur_chunk = 8
      self.modules.append(RomEntryRomHdr("Skip", skip, self.base_addr+2))
    # add entry
    self.modules.append(entry)
    self.cur_off += n
    self.cur_chunk += n
    return entry

  def add_module(self, name, data, relocs):
    e = RomEntryRaw(name, data, relocs)
    return self._add_entry(e)

  def add_bin_img(self, name, bin_img):
    e = RomEntryBinImg(name, bin_img)
    return self._add_entry(e)

  def build_rom(self):
    rom_data = bytearray(self.size_bytes)
    # fill in modules
    addr = self.base_addr
    off = 0
    for mod in self.modules:
      n = mod.get_size()
      rom_data[off: off+n] = mod.get_data(addr)
      off += n
      addr += n
    # fill space
    fill = chr(self.fill_byte)
    while off < self.size_bytes:
      rom_data[off] = fill
      off += 1
    # add kick sum
    if self.kick_sum:
      kh = KickRom.Helper(rom_data)
      kh.write_rom_size_field()
      kh.write_footer()
      kh.write_check_sum()
    return rom_data
