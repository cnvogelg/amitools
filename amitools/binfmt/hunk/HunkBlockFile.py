"""The hunk block types defined as data classes"""


import struct
from .Hunk import *


class HunkParseError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class HunkBlock:
    """Base class for all hunk block types"""

    blk_id = 0xDEADBEEF
    sub_offset = None  # used inside LIB

    def _read_long(self, f):
        """read a 4 byte long"""
        data = f.read(4)
        if len(data) != 4:
            raise HunkParseError("read_long failed")
        return struct.unpack(">I", data)[0]

    def _read_word(self, f):
        """read a 2 byte word"""
        data = f.read(2)
        if len(data) != 2:
            raise HunkParseError("read_word failed")
        return struct.unpack(">H", data)[0]

    def _read_name(self, f):
        """read name stored in longs
        return size, string
        """
        num_longs = self._read_long(f)
        if num_longs == 0:
            return 0, ""
        else:
            return self._read_name_size(f, num_longs)

    def _read_name_size(self, f, num_longs):
        size = (num_longs & 0xFFFFFF) * 4
        data = f.read(size)
        if len(data) < size:
            return -1, None
        endpos = data.find(b"\0")
        if endpos == -1:
            return size, data
        elif endpos == 0:
            return 0, ""
        else:
            return size, data[:endpos]

    def _write_long(self, f, v):
        data = struct.pack(">I", v)
        f.write(data)

    def _write_word(self, f, v):
        data = struct.pack(">H", v)
        f.write(data)

    def _write_name(self, f, s, tag=None):
        n = len(s)
        num_longs = int((n + 3) / 4)
        b = bytearray(num_longs * 4)
        if n > 0:
            b[0:n] = s
        if tag is not None:
            num_longs |= tag << 24
        self._write_long(f, num_longs)
        f.write(b)


class HunkHeaderBlock(HunkBlock):
    """HUNK_HEADER - header block of Load Modules"""

    blk_id = HUNK_HEADER

    def __init__(self):
        self.reslib_names = []
        self.table_size = 0
        self.first_hunk = 0
        self.last_hunk = 0
        self.hunk_table = []

    def setup(self, hunk_sizes):
        # easy setup for given number of hunks
        n = len(hunk_sizes)
        if n == 0:
            raise HunkParseError("No hunks for HUNK_HEADER given")
        self.table_size = n
        self.first_hunk = 0
        self.last_hunk = n - 1
        self.hunk_table = hunk_sizes

    def parse(self, f):
        # parse resident library names (AOS 1.x only)
        while True:
            l, s = self._read_name(f)
            if l < 0:
                raise HunkParseError("Error parsing HUNK_HEADER names")
            elif l == 0:
                break
            self.reslib_names.append(s)

        # table size and hunk range
        self.table_size = self._read_long(f)
        self.first_hunk = self._read_long(f)
        self.last_hunk = self._read_long(f)
        if self.table_size < 0 or self.first_hunk < 0 or self.last_hunk < 0:
            raise HunkParseError(
                "HUNK_HEADER invalid table_size or first_hunk or last_hunk"
            )

        # determine number of hunks in size table
        num_hunks = self.last_hunk - self.first_hunk + 1
        for a in range(num_hunks):
            hunk_size = self._read_long(f)
            if hunk_size < 0:
                raise HunkParseError("HUNK_HEADER contains invalid hunk_size")
            # note that the upper bits are the target memory type. We only have FAST,
            # so let's forget about them for a moment.
            self.hunk_table.append(hunk_size & 0x3FFFFFFF)

    def write(self, f):
        # write residents
        for reslib in self.reslib_names:
            self._write_name(f, reslib)
        self._write_long(f, 0)
        # table size and hunk range
        self._write_long(f, self.table_size)
        self._write_long(f, self.first_hunk)
        self._write_long(f, self.last_hunk)
        # sizes
        for hunk_size in self.hunk_table:
            self._write_long(f, hunk_size)


class HunkSegmentBlock(HunkBlock):
    """HUNK_CODE, HUNK_DATA, HUNK_BSS"""

    def __init__(self, blk_id=None, data=None, size_longs=0):
        if blk_id is not None:
            self.blk_id = blk_id
        self.data = data
        self.size_longs = size_longs

    def parse(self, f):
        size = self._read_long(f)
        self.size_longs = size
        if self.blk_id != HUNK_BSS:
            size *= 4
            self.data = f.read(size)

    def write(self, f):
        self._write_long(f, self.size_longs)
        f.write(self.data)


class HunkRelocLongBlock(HunkBlock):
    """HUNK_ABSRELOC32 - relocations stored in longs"""

    def __init__(self, blk_id=None, relocs=None):
        if blk_id is not None:
            self.blk_id = blk_id
        # map hunk number to list of relocations (i.e. byte offsets in long)
        if relocs is None:
            self.relocs = []
        else:
            self.relocs = relocs

    def parse(self, f):
        while True:
            num = self._read_long(f)
            if num == 0:
                break
            hunk_num = self._read_long(f)
            offsets = []
            for i in range(num):
                off = self._read_long(f)
                offsets.append(off)
            self.relocs.append((hunk_num, offsets))

    def write(self, f):
        for reloc in self.relocs:
            hunk_num, offsets = reloc
            self._write_long(f, len(offsets))
            self._write_long(f, hunk_num)
            for off in offsets:
                self._write_long(f, off)
        self._write_long(f, 0)


class HunkRelocWordBlock(HunkBlock):
    """HUNK_RELOC32SHORT - relocations stored in words"""

    def __init__(self, blk_id=None, relocs=None):
        if blk_id is not None:
            self.blk_id = blk_id
        # list of tuples (hunk_no, [offsets])
        if relocs is None:
            self.relocs = []
        else:
            self.relocs = relocs

    def parse(self, f):
        num_words = 0
        while True:
            num_offs = self._read_word(f)
            num_words += 1
            if num_offs == 0:
                break
            hunk_num = self._read_word(f)
            num_words += num_offs + 1
            offsets = []
            for i in range(num_offs):
                off = self._read_word(f)
                offsets.append(off)
            self.relocs.append((hunk_num, offsets))
        # pad to long
        if num_words % 2 == 1:
            self._read_word(f)

    def write(self, f):
        num_words = 0
        for hunk_num, offsets in self.relocs:
            num_offs = len(offsets)
            self._write_word(f, num_offs)
            self._write_word(f, hunk_num)
            for i in range(num_offs):
                self._write_word(f, offsets[i])
            num_words += 2 + num_offs
        # end
        self._write_word(f, 0)
        num_words += 1
        # padding?
        if num_words % 2 == 1:
            self._write_word(f, 0)


class HunkEndBlock(HunkBlock):
    """HUNK_END"""

    blk_id = HUNK_END

    def parse(self, f):
        pass

    def write(self, f):
        pass


class HunkOverlayBlock(HunkBlock):
    """HUNK_OVERLAY"""

    blk_id = HUNK_OVERLAY

    def __init__(self):
        self.data = None

    def parse(self, f):
        num_longs = self._read_long(f)
        self.data = f.read(num_longs * 4)

    def write(self, f):
        self._write_long(f, int(self.data / 4))
        f.write(self.data)


class HunkBreakBlock(HunkBlock):
    """HUNK_BREAK"""

    blk_id = HUNK_BREAK

    def parse(self, f):
        pass

    def write(self, f):
        pass


class HunkDebugBlock(HunkBlock):
    """HUNK_DEBUG"""

    blk_id = HUNK_DEBUG

    def __init__(self, debug_data=None):
        self.debug_data = debug_data

    def parse(self, f):
        num_longs = self._read_long(f)
        num_bytes = num_longs * 4
        self.debug_data = f.read(num_bytes)

    def write(self, f):
        num_longs = int(len(self.debug_data) / 4)
        self._write_long(f, num_longs)
        f.write(self.debug_data)


class HunkSymbolBlock(HunkBlock):
    """HUNK_SYMBOL"""

    blk_id = HUNK_SYMBOL

    def __init__(self, symbols=None):
        if symbols is None:
            self.symbols = []
        else:
            self.symbols = symbols

    def parse(self, f):
        while True:
            s, n = self._read_name(f)
            if s == 0:
                break
            off = self._read_long(f)
            self.symbols.append((n, off))

    def write(self, f):
        for sym, off in self.symbols:
            self._write_name(f, sym)
            self._write_long(f, off)
        self._write_long(f, 0)


class HunkUnitBlock(HunkBlock):
    """HUNK_UNIT"""

    blk_id = HUNK_UNIT

    def __init__(self):
        self.name = None

    def parse(self, f):
        _, self.name = self._read_name(f)

    def write(self, f):
        self._write_name(f, self.name)


class HunkNameBlock(HunkBlock):
    """HUNK_NAME"""

    blk_id = HUNK_NAME

    def __init__(self):
        self.name = None

    def parse(self, f):
        _, self.name = self._read_name(f)

    def write(self, f):
        self._write_name(f, self.name)


class HunkExtEntry:
    """helper class for HUNK_EXT entries"""

    def __init__(self, name, ext_type, value, bss_size, offsets):
        self.name = name
        self.ext_type = ext_type
        self.def_value = value  # defs only
        self.bss_size = bss_size  # ABSCOMMON only
        self.ref_offsets = offsets  # refs only: list of offsets


class HunkExtBlock(HunkBlock):
    """HUNK_EXT"""

    blk_id = HUNK_EXT

    def __init__(self):
        self.entries = []

    def parse(self, f):
        while True:
            tag = self._read_long(f)
            if tag == 0:
                break
            ext_type = tag >> 24
            name_len = tag & 0xFFFFFF
            _, name = self._read_name_size(f, name_len)
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
                for i in range(num_refs):
                    off = self._read_long(f)
                    offsets.append(off)
            # is a definition
            else:
                value = self._read_long(f)
            e = HunkExtEntry(name, ext_type, value, bss_size, offsets)
            self.entries.append(e)

    def write(self, f):
        for entry in self.entries:
            ext_type = entry.ext_type
            self._write_name(f, entry.name, tag=ext_type)
            # ABSCOMMON
            if ext_type == EXT_ABSCOMMON:
                self._write_long(f, entry.bss_size)
            # is a reference
            elif ext_type >= 0x80:
                num_offsets = len(entry.ref_offsets)
                self._write_long(f, num_offsets)
                for off in entry.ref_offsets:
                    self._write_long(f, off)
            # is a definition
            else:
                self._write_long(f, entry.def_value)
        self._write_long(f, 0)


class HunkLibBlock(HunkBlock):
    """HUNK_LIB"""

    blk_id = HUNK_LIB

    def __init__(self):
        self.blocks = []
        self.offsets = []

    def parse(self, f, isLoadSeg=False):
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
            blk_id = struct.unpack(">I", tag)[0]
            # mask out mem flags
            blk_id = blk_id & HUNK_TYPE_MASK
            # look up block type
            if blk_id in hunk_block_type_map:
                blk_type = hunk_block_type_map[blk_id]
                # create block and parse
                block = blk_type()
                block.blk_id = blk_id
                block.parse(f)
                self.offsets.append(pos)
                self.blocks.append(block)
            else:
                raise HunkParseError("Unsupported hunk type: %04d" % blk_id)
            pos = f.tell()

    def write(self, f):
        # write dummy length (fill in later)
        pos = f.tell()
        start = pos
        self._write_long(f, 0)
        self.offsets = []
        # write blocks
        for block in self.blocks:
            block_id = block.blk_id
            block_id_raw = struct.pack(">I", block_id)
            f.write(block_id_raw)
            # write block itself
            block.write(f)
            # update offsets
            self.offsets.append(pos)
            pos = f.tell()
        # fill in size
        end = f.tell()
        size = end - start - 4
        num_longs = size // 4
        f.seek(start, 0)
        self._write_long(f, num_longs)
        f.seek(end, 0)


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

    blk_id = HUNK_INDEX

    def __init__(self):
        self.strtab = None
        self.units = []

    def parse(self, f):
        num_longs = self._read_long(f)
        num_words = num_longs * 2
        # string table size
        strtab_size = self._read_word(f)
        self.strtab = f.read(strtab_size)
        num_words = num_words - (strtab_size // 2) - 1
        # read index unit blocks
        while num_words > 1:
            # unit description
            name_off = self._read_word(f)
            first_hunk_long_off = self._read_word(f)
            num_hunks = self._read_word(f)
            num_words -= 3
            unit_entry = HunkIndexUnitEntry(name_off, first_hunk_long_off)
            self.units.append(unit_entry)
            for i in range(num_hunks):
                # hunk description
                name_off = self._read_word(f)
                hunk_longs = self._read_word(f)
                hunk_ctype = self._read_word(f)
                hunk_entry = HunkIndexHunkEntry(name_off, hunk_longs, hunk_ctype)
                unit_entry.index_hunks.append(hunk_entry)
                # refs
                num_refs = self._read_word(f)
                for j in range(num_refs):
                    name_off = self._read_word(f)
                    hunk_entry.sym_refs.append(HunkIndexSymbolRef(name_off))
                # defs
                num_defs = self._read_word(f)
                for j in range(num_defs):
                    name_off = self._read_word(f)
                    value = self._read_word(f)
                    stype = self._read_word(f)
                    hunk_entry.sym_defs.append(
                        HunkIndexSymbolDef(name_off, value, stype)
                    )
                # calc word size
                num_words = num_words - (5 + num_refs + num_defs * 3)
        # alignment word?
        if num_words == 1:
            self._read_word(f)

    def write(self, f):
        # write dummy size
        num_longs_pos = f.tell()
        self._write_long(f, 0)
        num_words = 0
        # write string table
        size_strtab = len(self.strtab)
        self._write_word(f, size_strtab)
        f.write(self.strtab)
        num_words += size_strtab // 2 + 1
        # write unit blocks
        for unit in self.units:
            self._write_word(f, unit.name_off)
            self._write_word(f, unit.first_hunk_long_off)
            self._write_word(f, len(unit.index_hunks))
            num_words += 3
            for index in unit.index_hunks:
                self._write_word(f, index.name_off)
                self._write_word(f, index.hunk_longs)
                self._write_word(f, index.hunk_ctype)
                # refs
                num_refs = len(index.sym_refs)
                self._write_word(f, num_refs)
                for sym_ref in index.sym_refs:
                    self._write_word(f, sym_ref.name_off)
                # defs
                num_defs = len(index.sym_defs)
                self._write_word(f, num_defs)
                for sym_def in index.sym_defs:
                    self._write_word(f, sym_def.name_off)
                    self._write_word(f, sym_def.value)
                    self._write_word(f, sym_def.sym_ctype)
                # count words
                num_words += 5 + num_refs + num_defs * 3
        # alignment word?
        if num_words % 2 == 1:
            num_words += 1
            self._write_word(f, 0)
        # fill in real size
        pos = f.tell()
        f.seek(num_longs_pos, 0)
        self._write_long(f, num_words / 2)
        f.seek(pos, 0)


# map the hunk types to the block classes
hunk_block_type_map = {
    # Load Module
    HUNK_HEADER: HunkHeaderBlock,
    HUNK_CODE: HunkSegmentBlock,
    HUNK_DATA: HunkSegmentBlock,
    HUNK_BSS: HunkSegmentBlock,
    HUNK_ABSRELOC32: HunkRelocLongBlock,
    HUNK_RELOC32SHORT: HunkRelocWordBlock,
    HUNK_END: HunkEndBlock,
    HUNK_DEBUG: HunkDebugBlock,
    HUNK_SYMBOL: HunkSymbolBlock,
    # Overlays
    HUNK_OVERLAY: HunkOverlayBlock,
    HUNK_BREAK: HunkBreakBlock,
    # Object Module
    HUNK_UNIT: HunkUnitBlock,
    HUNK_NAME: HunkNameBlock,
    HUNK_RELRELOC16: HunkRelocLongBlock,
    HUNK_RELRELOC8: HunkRelocLongBlock,
    HUNK_DREL32: HunkRelocLongBlock,
    HUNK_DREL16: HunkRelocLongBlock,
    HUNK_DREL8: HunkRelocLongBlock,
    HUNK_EXT: HunkExtBlock,
    # New Library
    HUNK_LIB: HunkLibBlock,
    HUNK_INDEX: HunkIndexBlock,
}


class HunkBlockFile:
    """The HunkBlockFile holds the list of blocks found in a hunk file"""

    def __init__(self, blocks=None):
        if blocks is None:
            self.blocks = []
        else:
            self.blocks = blocks

    def get_blocks(self):
        return self.blocks

    def set_blocks(self, blocks):
        self.blocks = blocks

    def read_path(self, path_name, isLoadSeg=False, verbose=False):
        f = open(path_name, "rb")
        self.read(f, isLoadSeg, verbose)
        f.close()

    def read(self, f, isLoadSeg=False, verbose=False):
        """read a hunk file and fill block list"""
        while True:
            # first read block id
            tag = f.read(4)
            # EOF
            if len(tag) == 0:
                break
            elif len(tag) != 4:
                raise HunkParseError("Hunk block tag too short!")
            blk_id = struct.unpack(">I", tag)[0]
            # mask out mem flags
            blk_id = blk_id & HUNK_TYPE_MASK
            # look up block type
            if blk_id in hunk_block_type_map:
                # v37 special case: 1015 is 1020 (HUNK_RELOC32SHORT)
                # we do this only in LoadSeg() files
                if isLoadSeg and blk_id == 1015:
                    blk_id = 1020
                blk_type = hunk_block_type_map[blk_id]
                # create block and parse
                block = blk_type()
                block.blk_id = blk_id
                block.parse(f)
                self.blocks.append(block)
            else:
                raise HunkParseError("Unsupported hunk type: %04d" % blk_id)

    def write_path(self, path_name):
        f = open(path_name, "wb")
        self.write(f)
        f.close()

    def write(self, f, isLoadSeg=False):
        """write a hunk file back to file object"""
        for block in self.blocks:
            # write block id
            block_id = block.blk_id
            # convert id
            if isLoadSeg and block_id == 1020:
                block_id = 1015
            block_id_raw = struct.pack(">I", block_id)
            f.write(block_id_raw)
            # write block itself
            block.write(f)

    def detect_type(self):
        """look at blocks and try to deduce the type of hunk file"""
        if len(self.blocks) == 0:
            return TYPE_UNKNOWN
        first_block = self.blocks[0]
        blk_id = first_block.blk_id
        return self._map_blkid_to_type(blk_id)

    def peek_type(self, f):
        """look into given file obj stream to determine file format.
        stream is read and later on seek'ed back."""
        pos = f.tell()
        tag = f.read(4)
        # EOF
        if len(tag) == 0:
            return TYPE_UNKNOWN
        elif len(tag) != 4:
            f.seek(pos, 0)
            return TYPE_UNKNOWN
        else:
            blk_id = struct.unpack(">I", tag)[0]
            f.seek(pos, 0)
            return self._map_blkid_to_type(blk_id)

    def _map_blkid_to_type(self, blk_id):
        if blk_id == HUNK_HEADER:
            return TYPE_LOADSEG
        elif blk_id == HUNK_UNIT:
            return TYPE_UNIT
        elif blk_id == HUNK_LIB:
            return TYPE_LIB
        else:
            return TYPE_UNKNOWN

    def get_block_type_names(self):
        """return a string array with the names of all block types"""
        res = []
        for blk in self.blocks:
            blk_id = blk.blk_id
            name = hunk_names[blk_id]
            res.append(name)
        return res


# mini test
if __name__ == "__main__":
    import sys
    import io

    for a in sys.argv[1:]:
        # read data
        f = open(a, "rb")
        data = f.read()
        f.close()
        # parse from string stream
        fobj = io.StringIO(data)
        hbf = HunkBlockFile()
        hbf.read(fobj, True)
        fobj.close()
        print(hbf.blocks)
        # write to new string stream
        nobj = io.StringIO()
        hbf.write(nobj, True)
        new_data = nobj.getvalue()
        nobj.close()
        # dump debug data
        f = open("debug.hunk", "wb")
        f.write(new_data)
        f.close()
        # compare read and written stream
        if len(data) != len(new_data):
            print("MISMATCH", len(data), len(new_data))
        else:
            for i in range(len(data)):
                if data[i] != new_data[i]:
                    print("MISMATCH @%x" % i)
            print("OK")
        # detect type of file
        t = hbf.detect_type()
        print("type=", t, type_names[t])
