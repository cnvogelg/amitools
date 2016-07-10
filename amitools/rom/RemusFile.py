from __future__ import print_function

import os
import struct


class RemusRom(object):
  def __init__(self, sum_off, chk_sum, size, base_addr, name, short_name):
    self.sum_off = sum_off
    self.chk_sum = chk_sum
    self.size = size
    self.base_addr = base_addr
    self.name = name
    self.short_name = short_name
    self.entries = []

  def __repr__(self):
    return "RemusRom(sum_off=%08x,chk_sum=%08x,size=%08x,base_addr=%08x," \
           "name=%s,short_name=%s)" % \
           (self.sum_off, self.chk_sum, self.size, self.base_addr,
            self.name, self.short_name)


class RemusRomEntry(object):
  def __init__(self, name, offset, size, reloc_off):
    self.name = name
    self.offset = offset
    self.size = size
    self.reloc_off = reloc_off
    self.relocs = []

  def __repr__(self):
    return "RemusRomEntry(name=%s,offset=%08x,size=%08x,reloc_off=%08x)" % \
           (self.name, self.offset, self.size, self.reloc_off)


class RemusFile(object):
  def __init__(self, header):
    self.data = None
    self.offset = 0
    self.header = header

  def load(self, path):
    with open(path, "rb") as fh:
      self.data = fh.read()
    self.offset = 0
    # check header
    l = self._read_long()
    if l != self.header:
      raise IOError("Wrong header! %08x != %08x" % (self.header, l))
    # skip version
    l = self._read_long()

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
    res = ""
    while True:
      if ord(self.data[pos]) == 0:
        break
      res += self.data[pos]
      pos+=1
    return res


class RemusSplitFile(RemusFile):
  def __init__(self):
    RemusFile.__init__(self, 0x524d5346)
    self.roms = []

  def load(self, path):
    RemusFile.load(self, path)
    self.roms = []
    u32_max = 0xffffffff
    # loop: new rom
    while True:
      # parse rom entry
      num_entries = self._read_long()
      if num_entries == u32_max:
        break
      sum_off = self._read_long()
      chk_sum = self._read_long()
      size = self._read_long()
      name_off = self._read_long()
      base_addr = self._read_long()
      short_name_off = self._read_long()
      name = self._read_string(name_off)
      short_name = self._read_string(short_name_off)
      rom = RemusRom(sum_off, chk_sum, size, base_addr,
                     name, short_name)
      self.roms.append(rom)
      # now parse entries for this rom
      while True:
        name_off = self._read_long()
        if name_off == u32_max:
          break
        offset = self._read_long()
        size = self._read_long()
        reloc_off = self._read_long()
        name = self._read_string(name_off)
        entry = RemusRomEntry(name, offset, size, reloc_off)
        rom.entries.append(entry)
      assert len(rom.entries) == num_entries
      # sort entry by offset
      rom.entries.sort(key=lambda x: x.offset)
    # parse relocs
    for rom in self.roms:
      for entry in rom.entries:
        off = entry.reloc_off
        num_relocs = self._read_long(off)
        if num_relocs != u32_max:
          for i in xrange(num_relocs):
            off += 4
            reloc_off = self._read_long(off)
            entry.relocs.append(reloc_off)

  def dump(self):
    for rom in self.roms:
      print("#%04x  @%08x  +%08x  %08x: %08x  %-24s  %s" %
            (len(rom.entries), rom.base_addr, rom.size,
             rom.sum_off, rom.chk_sum,
             rom.short_name, rom.name))

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
    return "RemusIdEntry(count=%x,bogus=%08x,chk_sum=%08x,name=%s" % \
           (self.count, self.bogus, self.chk_sum, self.name)


class RemusIdFile(RemusFile):
  def __init__(self):
    RemusFile.__init__(self, 0x524d4944)
    self.entries = []

  def load(self, path):
    RemusFile.load(self, path)
    u16_max = 0xffff
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
    # load *.dat files
    for f in os.listdir(data_dir):
      file = os.path.join(data_dir, f)
      if file.endswith(".dat"):
        sf = RemusSplitFile()
        sf.load(file)
        self.split_files.append(sf)
    # id file?
    id_file = os.path.join(data_dir, "romid.idat")
    if os.path.exists(id_file):
      si = RemusIdFile()
      si.load(id_file)
      self.id_file = si

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
    roms = sorted(roms, key=lambda x:x.name)
    return roms


if __name__ == '__main__':
  import sys
  import KickRom
  rfs = RemusFileSet()
  rfs.load("../data/splitdata")
  rfs.dump()
  if len(sys.argv) > 0:
    for rom_path in sys.argv[1:]:
      rom_img = KickRom.Loader.load(rom_path)
      kh = KickRom.Helper(rom_img)
      if kh.is_kick_rom():
        chk_sum = kh.read_check_sum()
      else:
        chk_sum = kh.calc_check_sum()
      found_rom = rfs.find_rom(rom_img, chk_sum)
      print(found_rom)
