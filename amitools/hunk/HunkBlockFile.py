"""The hunk block types defined as data classes"""

import struct
from Hunk import *


class HunkParseError(Exception):
  def __init__(self, msg):
    self.msg = msg

  def __str__(self):
    return self.msg


class HunkBlock:
  """Base class for all hunk block types"""

  blk_id = 0
  sub_offset = None # used inside LIB

  def _read_long(self, f):
    """read a 4 byte long"""
    data = f.read(4)
    if len(data) != 4:
      raise HunkParseError("read_long failed")
    return struct.unpack(">I",data)[0]

  def _read_word(self, f):
    """read a 2 byte word"""
    data = f.read(2)
    if len(data) != 2:
      raise HunkParseError("read_word failed")
    return struct.unpack(">H",data)[0]

  def _read_name(self, f):
    """read name stored in longs
       return size, string
    """
    num_longs = self._read_long(f)
    if num_longs == 0:
      return 0,""
    else:
      return self._read_name_size(f, num_longs)

  def _read_name_size(self, f, num_longs):
    size = (num_longs & 0xffffff) * 4
    data = f.read(size)
    if len(data) < size:
      return -1,None
    endpos = data.find('\0')
    if endpos == -1:
      return size,data
    elif endpos == 0:
      return 0,""
    else:
      return size,data[:endpos]


class HunkHeaderBlock(HunkBlock):
  """HUNK_HEADER - header block of Load Modules"""
  def __init__(self):
    self.reslib_names = []
    self.table_size = 0
    self.first_hunk = 0
    self.last_hunk = 0
    self.hunk_table = []

  def parse(self, f):
    # parse resident library names (AOS 1.x only)
    while True:
      l,s = self._read_name(f)
      if l < 0:
        raise HunkParseError("Error parsing HUNK_HEADER names")
      elif l == 0:
        break
      self.reslib_names.append(s)

    # table size and hunk range
    self.table_size = self._read_long(f)
    self.first_hunk = self._read_long(f)
    self.last_hunk  = self._read_long(f)
    if self.table_size < 0 or self.first_hunk < 0 or self.last_hunk < 0:
      raise HunkParseError("HUNK_HEADER invalid table_size or first_hunk or last_hunk")

    # determine number of hunks in size table
    num_hunks = self.last_hunk - self.first_hunk + 1
    for a in xrange(num_hunks):
      hunk_size = self._read_long(f)
      if hunk_size < 0:
        raise HunkParseError("HUNK_HEADER contains invalid hunk_size")
      self.hunk_table.append(hunk_size)


class HunkSegmentBlock(HunkBlock):
  """HUNK_CODE, HUNK_DATA, HUNK_BSS"""
  def __init__(self):
    self.data = None
    self.size_longs = 0

  def parse(self, f):
    size = self._read_long(f)
    self.size_longs = size
    if self.blk_id != HUNK_BSS:
      size *= 4
      self.data = f.read(size)


class HunkRelocLongBlock(HunkBlock):
  """HUNK_ABSRELOC32 - relocations stored in longs"""
  def __init__(self):
    # map hunk number to list of relocations (i.e. byte offsets in long)
    self.relocs = {}

  def parse(self, f):
    while True:
      num = self._read_long(f)
      if num == 0:
        break
      hunk_num = self._read_long(f)
      offsets = []
      for i in xrange(num):
        off = self._read_long(f)
        offsets.append(off)
      self.relocs[hunk_num] = offsets


class HunkRelocWordBlock(HunkBlock):
  """HUNK_RELOC32SHORT - relocations stored in words"""
  def __init__(self):
    # list of tuples (hunk_no, [offsets])
    self.relocs = []

  def parse(self, f):
    num_words = 0
    while True:
      num = self._read_word(f)
      num_words = num_words + 1
      if num == 0:
        break
      hunk_num = self._read_word(f)
      num_words = num_words + num + 1
      offsets = []
      for i in xrange(num):
        off = self._read_word(f)
        offsets.append(off)
      self.relocs.append((hunk_num, offsets))
    # pad to long
    if num_words % 1 == 1:
      self._read_word(f)


class HunkEndBlock(HunkBlock):
  """HUNK_END"""
  def parse(self, f):
    pass


class HunkOverlayEntry:
  def __init__(self, seek_offset, dummy1, dummy2, level, ordinate,
               initial_hunk, symbol_hunk, symbol_offset):
    self.seek_offset = seek_offset
    self.dummy1 = dummy1
    self.dummy2 = dummy2
    self.level = level
    self.ordinate = ordinate
    self.initial_hunk = initial_hunk
    self.symbol_hunk = symbol_hunk
    self.symbol_offset = symbol_offset


class HunkOverlayBlock(HunkBlock):
  """HUNK_OVERLAY"""
  def __init__(self):
    self.data = None

  def parse(self, f):
    num_longs = self._read_long(f)
    self.data = f.read(num_longs * 4)


class HunkBreakBlock(HunkBlock):
  """HUNK_BREAK"""
  def parse(self, f):
    pass


class HunkDebugBlock(HunkBlock):
  """HUNK_DEBUG"""
  def __init__(self):
    self.debug_data = None

  def parse(self, f):
    num_longs = self._read_long(f)
    num_bytes = num_longs * 4
    self.debug_data = f.read(num_bytes)


class HunkSymbolBlock(HunkBlock):
  """HUNK_SYMBOL"""
  def __init__(self):
    self.symbols = []

  def parse(self, f):
    while True:
      s,n = self._read_name(f)
      if s == 0:
        break
      off = self._read_long(f)
      self.symbols.append((n, off))


class HunkUnitBlock(HunkBlock):
  """HUNK_UNIT"""
  def __init__(self):
    self.name = None

  def parse(self, f):
    _,self.name = self._read_name(f)


class HunkNameBlock(HunkBlock):
  """HUNK_NAME"""
  def __init__(self):
    self.name = None

  def parse(self, f):
    _,self.name = self._read_name(f)


class HunkExtEntry:
  """helper class for HUNK_EXT entries"""
  def __init__(self, name, ext_type, value, bss_size, offsets):
    self.name = name
    self.ext_type = ext_type
    self.def_value = value # defs only
    self.bss_size = bss_size # ABSCOMMON only
    self.ref_offsets = offsets # refs only: list of offsets


class HunkExtBlock(HunkBlock):
  """HUNK_EXT"""
  def __init__(self):
    self.entries = []

  def parse(self, f):
    while True:
      tag = self._read_long(f)
      if tag == 0:
        break
      ext_type = tag >> 24
      name_len = tag & 0xffffff
      name = self._read_name_size(f, name_len)
      # add on for type
      bss_size = None
      offsets = None
      value = None
      # ABSCOMMON -> bss size
      if ext_type == EXT_ABSCOMMON:
        bss_size = self._read_long(f)
      # is a reference
      elif ext_type >= 0x80:
        num_refs = self._read_long(f)
        offsets = []
        for i in xrange(num_refs):
          off = self._read_long(f)
          offsets.append(off)
      # is a definition
      else:
          value = self._read_long(f)
      e = HunkExtEntry(name, ext_type, value, bss_size, offsets)
      self.entries.append(e)


class HunkLibBlock(HunkBlock):
  """HUNK_LIB"""
  def __init__(self):
    self.blocks = []

  def parse(self, f):
    num_longs = self._read_long(f)
    pos = f.tell()
    end_pos = pos + num_longs * 4
    # first read block id
    while pos < end_pos:
      tag = f.read(4)
      # EOF
      if len(tag) == 0:
        break
      elif len(tag) != 4:
        raise HunkParseError("Hunk block tag too short!")
      blk_id = struct.unpack(">I",tag)[0]
      # mask out mem flags
      blk_id = blk_id & HUNK_TYPE_MASK
      # look up block type
      if blk_id in hunk_block_type_map:
        blk_type = hunk_block_type_map[blk_id]
        # create block and parse
        block = blk_type()
        block.blk_id = blk_id
        block.sub_offset = pos
        block.parse(f)
        self.blocks.append(block)
      else:
        raise HunkParseError("Unsupported hunk type: %04d" % blk_id)
      pos = f.tell()


class HunkIndexUnitEntry:
  def __init__(self, name_off, first_hunk_long_off):
    self.name_off = name_off
    self.first_hunk_long_off = first_hunk_long_off
    self.index_hunks = []


class HunkIndexHunkEntry:
  def __init__(self, name_off, hunk_longs, hunk_ctype):
    self.name_off = name_off
    self.hunk_longs = hunk_longs
    self.hunk_ctype = hunk_ctype
    self.sym_refs = []
    self.sym_defs = []


class HunkIndexSymbolRef:
  def __init__(self, name_off):
    self.name_off = name_off


class HunkIndexSymbolDef:
  def __init__(self, name_off, value, sym_ctype):
    self.name_off = name_off
    self.value = value
    self.sym_ctype = sym_ctype


class HunkIndexBlock(HunkBlock):
  """HUNK_INDEX"""
  def __init__(self):
    self.strtab = None
    self.units = []

  def parse(self, f):
    num_longs = self._read_long(f)
    num_words = num_longs * 2
    # string table size
    strtab_size = self._read_word(f)
    self.strtab = f.read(strtab_size)
    num_words = num_words - (strtab_size / 2) - 1
    # read index unit blocks
    while num_words > 1:
      # unit description
      name_off = self._read_word(f)
      first_hunk_long_off = self._read_word(f)
      num_hunks = self._read_word(f)
      num_words = num_words - 3
      unit_entry = HunkIndexUnitEntry(name_off, first_hunk_long_off)
      self.units.append(unit_entry)
      for i in xrange(num_hunks):
        # hunk description
        name_off = self._read_word(f)
        hunk_longs = self._read_word(f)
        hunk_ctype = self._read_word(f)
        hunk_entry = HunkIndexHunkEntry(name_off, hunk_longs, hunk_ctype)
        unit_entry.index_hunks.append(hunk_entry)
        # refs
        num_refs = self._read_word(f)
        for j in xrange(num_refs):
          name_off = self._read_word(f)
          hunk_entry.sym_refs.append(HunkIndexSymbolRef(name_off))
        # defs
        num_defs = self._read_word(f)
        for j in xrange(num_defs):
          name_off = self._read_word(f)
          value = self._read_word(f)
          stype = self._read_word(f)
          hunk_entry.sym_defs.append(HunkIndexSymbolDef(name_off, value, stype))
        # calc word size
        num_words = num_words - (5 + num_refs + num_defs * 3)
    # alignment word?
    if num_words == 1:
      self._read_word(f)


# map the hunk types to the block classes
hunk_block_type_map = {
  # Load Module
  HUNK_HEADER : HunkHeaderBlock,
  HUNK_CODE : HunkSegmentBlock,
  HUNK_DATA : HunkSegmentBlock,
  HUNK_BSS : HunkSegmentBlock,
  HUNK_ABSRELOC32 : HunkRelocLongBlock,
  HUNK_RELOC32SHORT : HunkRelocWordBlock,
  HUNK_END : HunkEndBlock,
  HUNK_DEBUG : HunkDebugBlock,
  HUNK_SYMBOL : HunkSymbolBlock,
  # Overlays
  HUNK_OVERLAY : HunkOverlayBlock,
  HUNK_BREAK : HunkBreakBlock,
  # Object Module
  HUNK_UNIT : HunkUnitBlock,
  HUNK_NAME : HunkNameBlock,
  HUNK_RELRELOC16 : HunkRelocLongBlock,
  HUNK_RELRELOC8 : HunkRelocLongBlock,
  HUNK_DREL32 : HunkRelocLongBlock,
  HUNK_DREL16 : HunkRelocLongBlock,
  HUNK_DREL8 : HunkRelocLongBlock,
  HUNK_EXT : HunkExtBlock,
  # New Library
  HUNK_LIB : HunkLibBlock,
  HUNK_INDEX : HunkIndexBlock
}


class HunkBlockFile:
  """The HunkBlockFile holds the list of blocks found in a hunk file"""
  def __init__(self):
    self.blocks = []

  def read(self, f):
    """read a hunk file and fill block list"""
    while True:
      # first read block id
      tag = f.read(4)
      # EOF
      if len(tag) == 0:
        break
      elif len(tag) != 4:
        raise HunkParseError("Hunk block tag too short!")
      blk_id = struct.unpack(">I",tag)[0]
      # mask out mem flags
      blk_id = blk_id & HUNK_TYPE_MASK
      # look up block type
      if blk_id in hunk_block_type_map:
        blk_type = hunk_block_type_map[blk_id]
        # create block and parse
        block = blk_type()
        block.blk_id = blk_id
        block.parse(f)
        self.blocks.append(block)
      else:
        raise HunkParseError("Unsupported hunk type: %04d" % blk_id)


# mini test
if __name__ == '__main__':
  import sys
  for a in sys.argv[1:]:
    f = open(a, "rb")
    hbf = HunkBlockFile()
    hbf.read(f)
    f.close()
