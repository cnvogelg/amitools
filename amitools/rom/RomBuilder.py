import struct

from amitools.binfmt.BinImage import *
from amitools.binfmt.Relocate import *


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


class RomBuilder:
  def __init__(self, size=512, base_addr=0xf8000, fill_byte=0xff):
    self.size = size # in KiB
    self.base_addr = base_addr
    self.fill_byte = fill_byte
    # state
    self.modules = []
    self.cur_off = 0
    self.max_bytes = size * 1024
    self.error = None

  def get_current_offset(self):
    return self.cur_off

  def get_bytes_left(self):
    return self.max_bytes - self.cur_off

  def does_fit(self, num_bytes):
    return self.cur_off + num_bytes < self.max_bytes

  def _add_entry(self, entry):
    n = entry.get_size()
    if not self.does_fit(n):
      self.error = "module '%s' does not fit into ROM!" % (name)
      return None
    self.modules.append(entry)
    self.cur_off += n
    return entry

  def add_module(self, name, data, relocs):
    e = RomEntryRaw(name, data, relocs)
    return self._add_entry(e)

  def add_bin_img(self, name, bin_img):
    e = RomEntryBinImg(name, bin_img)
    return self._add_entry(e)

  def build_rom(self):
    rom_data = bytearray(self.max_bytes)
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
    while off < self.max_bytes:
      rom_data[off] = fill
      off += 1
    return rom_data
