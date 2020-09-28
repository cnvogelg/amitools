from .HunkBlockFile import *
from .HunkDebug import HunkDebug


class HunkSegment:
    """holds a code, data, or bss hunk/segment"""

    def __init__(self):
        self.blocks = None
        self.seg_blk = None
        self.symbol_blk = None
        self.reloc_blks = None
        self.debug_blks = None
        self.debug_infos = None

    def __repr__(self):
        return "[seg=%s,symbol=%s,reloc=%s,debug=%s,debug_info=%s]" % (
            self._blk_str(self.seg_blk),
            self._blk_str(self.symbol_blk),
            self._blk_str_list(self.reloc_blks),
            self._blk_str_list(self.debug_blks),
            self._debug_infos_str(),
        )

    def setup_code(self, data):
        data, size_longs = self._pad_data(data)
        self.seg_blk = HunkSegmentBlock(HUNK_CODE, data, size_longs)

    def setup_data(self, data):
        data, size_longs = self._pad_data(data)
        self.seg_blk = HunkSegmentBlock(HUNK_DATA, data, size_longs)

    def _pad_data(self, data):
        size_bytes = len(data)
        bytes_mod = size_bytes % 4
        if bytes_mod > 0:
            add = 4 - bytes_mod
            data = data + "\0" * add
        size_long = int((size_bytes + 3) / 4)
        return data, size_long

    def setup_bss(self, size_bytes):
        size_longs = int((size_bytes + 3) / 4)
        self.seg_blk = HunkSegmentBlock(HUNK_BSS, None, size_longs)

    def setup_relocs(self, relocs, force_long=False):
        """relocs: ((hunk_num, (off1, off2, ...)), ...)"""
        if force_long:
            use_short = False
        else:
            use_short = self._are_relocs_short(relocs)
        if use_short:
            self.reloc_blks = [HunkRelocWordBlock(HUNK_RELOC32SHORT, relocs)]
        else:
            self.reloc_blks = [HunkRelocLongBlock(HUNK_ABSRELOC32, relocs)]

    def setup_symbols(self, symbols):
        """symbols: ((name, off), ...)"""
        self.symbol_blk = HunkSymbolBlock(symbols)

    def setup_debug(self, debug_info):
        if self.debug_infos is None:
            self.debug_infos = []
        self.debug_infos.append(debug_info)
        hd = HunkDebug()
        debug_data = hd.encode(debug_info)
        blk = HunkDebugBlock(debug_data)
        if self.debug_blks is None:
            self.debug_blks = []
        self.debug_blks.append(blk)

    def _are_relocs_short(self, relocs):
        for hunk_num, offsets in relocs:
            for off in offsets:
                if off > 65535:
                    return False
        return True

    def _debug_infos_str(self):
        if self.debug_infos is None:
            return "n/a"
        else:
            return ",".join(map(str, self.debug_infos))

    def _blk_str(self, blk):
        if blk is None:
            return "n/a"
        else:
            return hunk_names[blk.blk_id]

    def _blk_str_list(self, blk_list):
        res = []
        if blk_list is None:
            return "n/a"
        for blk in blk_list:
            res.append(hunk_names[blk.blk_id])
        return ",".join(res)

    def parse(self, blocks):
        hd = HunkDebug()
        self.blocks = blocks
        for blk in blocks:
            blk_id = blk.blk_id
            if blk_id in loadseg_valid_begin_hunks:
                self.seg_blk = blk
            elif blk_id == HUNK_SYMBOL:
                if self.symbol_blk is None:
                    self.symbol_blk = blk
                else:
                    raise HunkParserError("duplicate symbols in hunk")
            elif blk_id == HUNK_DEBUG:
                if self.debug_blks is None:
                    self.debug_blks = []
                self.debug_blks.append(blk)
                # decode hunk debug info
                debug_info = hd.decode(blk.debug_data)
                if debug_info is not None:
                    if self.debug_infos is None:
                        self.debug_infos = []
                    self.debug_infos.append(debug_info)
            elif blk_id in (HUNK_ABSRELOC32, HUNK_RELOC32SHORT):
                if self.reloc_blks is None:
                    self.reloc_blks = []
                self.reloc_blks.append(blk)
            else:
                raise HunkParseError("invalid hunk block")

    def create(self, blocks):
        # already has blocks?
        if self.blocks is not None:
            blocks += self.blocks
            return self.seg_blk.size_longs
        # start with segment block
        if self.seg_blk is None:
            raise HunkParseError("no segment block!")
        self.blocks = [self.seg_blk]
        # has relocations
        if self.reloc_blks is not None:
            self.blocks += self.reloc_blks
        # has debug?
        if self.debug_blks is not None:
            self.blocks += self.debug_blks
        # has symbols?
        if self.symbol_blk is not None:
            self.blocks.append(self.symbol_blk)
        # store blocks
        blocks += self.blocks
        # return size of segment
        return self.seg_blk.size_longs


class HunkLoadSegFile:
    """manage a LoadSeg() hunk file starting with HUNK_HEADER"""

    def __init__(self):
        self.hdr_blk = None
        self.segments = []

    def get_segments(self):
        return self.segments

    def add_segment(self, seg):
        self.segments.append(seg)

    def parse_block_file(self, bf):
        """assign hunk blocks into segments"""
        # get file blocks
        blks = bf.get_blocks()
        if blks is None or len(blks) == 0:
            raise HunkParseError("no hunk blocks found!")
        # ensure its a HUNK_HEADER
        hdr_blk = blks[0]
        if hdr_blk.blk_id != HUNK_HEADER:
            raise HunkParseError("no HEADER block found!")
        self.hdr_blk = hdr_blk
        # first round: split block list into sections seperated by END
        first = []
        cur = None
        for blk in blks[1:]:
            blk_id = blk.blk_id
            # split by END block
            if blk_id == HUNK_END:
                cur = None
            # add non end block to list
            else:
                # check validity of block
                if (
                    blk_id not in loadseg_valid_begin_hunks
                    and blk_id not in loadseg_valid_extra_hunks
                ):
                    raise HunkParseError("invalid block found: %d" % blk_id)
                if cur is None:
                    cur = []
                    first.append(cur)
                cur.append(blk)
        # second round: split list if two segments are found in a single list
        # this is only necessary for broken files that lack END blocks
        second = []
        for l in first:
            pos_seg = []
            off = 0
            for blk in l:
                if blk.blk_id in loadseg_valid_begin_hunks:
                    pos_seg.append(off)
                off += 1
            n = len(pos_seg)
            if n == 1:
                # list is ok
                second.append(l)
            elif n > 1:
                # list needs split
                # we can only split if no extra block is before next segment block
                new_list = None
                for blk in l:
                    if blk.blk_id in loadseg_valid_begin_hunks:
                        new_list = [blk]
                        second.append(new_list)
                    elif new_list is not None:
                        new_list.append(blk)
                    else:
                        raise HunkParseError("can't split block list")
        # check size of hunk table
        if len(hdr_blk.hunk_table) != len(second):
            raise HunkParseError("can't match hunks to header")
        # convert block lists into segments
        for l in second:
            seg = HunkSegment()
            seg.parse(l)
            self.segments.append(seg)
        # set size in segments
        n = len(second)
        for i in range(n):
            self.segments[i].size_longs = hdr_blk.hunk_table[i]
            self.segments[i].size = self.segments[i].size_longs * 4

    def create_block_file(self):
        """create a HunkBlockFile from the segments given"""
        # setup header block
        self.hdr_blk = HunkHeaderBlock()
        blks = [self.hdr_blk]
        sizes = []
        for seg in self.segments:
            size = seg.create(blks)
            sizes.append(size)
            # add HUNK_END
            blks.append(HunkEndBlock())
        # finally setup header
        self.hdr_blk.setup(sizes)
        # create HunkBlockFile
        return HunkBlockFile(blks)


# mini test
if __name__ == "__main__":
    import sys

    for a in sys.argv[1:]:
        bf = HunkBlockFile()
        bf.read_path(a, isLoadSeg=True)
        print(bf.get_block_type_names())
        lsf = HunkLoadSegFile()
        lsf.parse_block_file(bf)
        print(lsf.get_segments())
        # write back
        new_bf = lsf.create_block_file()
        new_bf.write_path("a.out")
        # compare read and written stream
        with open(a, "rb") as fh:
            data = fh.read()
        with open("a.out", "rb") as fh:
            new_data = fh.read()
        if len(data) != len(new_data):
            print("MISMATCH", len(data), len(new_data))
        else:
            for i in range(len(data)):
                if data[i] != new_data[i]:
                    print("MISMATCH @%x" % i)
            print("OK")
