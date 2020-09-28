from amitools.binfmt.BinImage import *
from .HunkBlockFile import HunkBlockFile, HunkParseError
from .HunkLoadSegFile import HunkLoadSegFile, HunkSegment
from .HunkDebug import *
from . import Hunk


class BinFmtHunk:
    """Handle Amiga's native Hunk file format"""

    def is_image(self, path):
        """check if a given file is a hunk LoadSeg file"""
        with open(path, "rb") as f:
            return self.is_image_fobj(f)

    def is_image_fobj(self, fobj):
        """check if a given fobj is a hunk LoadSeg file"""
        bf = HunkBlockFile()
        bf_type = bf.peek_type(fobj)
        return bf_type == Hunk.TYPE_LOADSEG

    def load_image(self, path):
        """load a BinImage from a hunk file given via path"""
        with open(path, "rb") as f:
            return self.load_image_fobj(f)

    def load_image_fobj(self, fobj):
        """load a BinImage from a hunk file given via file obj"""
        # read the hunk blocks
        bf = HunkBlockFile()
        bf.read(fobj, isLoadSeg=True)
        # derive load seg file
        lsf = HunkLoadSegFile()
        lsf.parse_block_file(bf)
        # convert load seg file
        return self.create_image_from_load_seg_file(lsf)

    def save_image(self, path, bin_img):
        """save a BinImage to a hunk file given via path"""
        with open(path, "wb") as f:
            self.save_image_fobj(f, bin_img)

    def save_image_fobj(self, fobj, bin_img):
        """save a BinImage to a hunk file given via file obj"""
        lsf = self.create_load_seg_file_from_image(bin_img)
        bf = lsf.create_block_file()
        bf.write(fobj, isLoadSeg=True)

    def create_load_seg_file_from_image(self, bin_img):
        """create a HunkLodSegFile from a BinImage"""
        lsf = HunkLoadSegFile()
        for seg in bin_img.segments:
            seg_type = seg.get_type()
            # create HunkSegment
            lseg = HunkSegment()
            lsf.add_segment(lseg)
            if seg_type == SEGMENT_TYPE_CODE:
                lseg.setup_code(seg.data)
            elif seg_type == SEGMENT_TYPE_DATA:
                lseg.setup_data(seg.data)
            elif seg_type == SEGMENT_TYPE_BSS:
                lseg.setup_bss(seg.size)
            else:
                raise HunkParseError("Unknown Segment Type in BinImage: %d" % seg_type)
            # add relocs
            self._add_bin_img_relocs(lseg, seg)
            # add symbols
            self._add_bin_img_symbols(lseg, seg)
            # add debug info
            self._add_bin_img_debug_info(lseg, seg)
        return lsf

    def _add_bin_img_relocs(self, hunk_seg, seg):
        reloc_segs = seg.get_reloc_to_segs()
        hunk_relocs = []
        for reloc_seg in reloc_segs:
            seg_id = reloc_seg.id
            reloc = seg.get_reloc(reloc_seg)
            relocs = reloc.get_relocs()
            offsets = []
            for r in relocs:
                if r.get_width() != 2 or r.get_addend() != 0:
                    raise HunkParseError("Invalid reloc: " + r)
                offsets.append(r.get_offset())
            hunk_relocs.append((seg_id, offsets))
        if len(hunk_relocs) > 0:
            hunk_seg.setup_relocs(hunk_relocs)

    def _add_bin_img_symbols(self, hunk_seg, seg):
        sym_tab = seg.get_symtab()
        if sym_tab is not None:
            hunk_sym_list = []
            for sym in sym_tab.get_symbols():
                hunk_sym_list.append((sym.get_name(), sym.get_offset()))
            hunk_seg.setup_symbols(hunk_sym_list)

    def _add_bin_img_debug_info(self, hunk_seg, seg):
        debug_line = seg.get_debug_line()
        if debug_line is not None:
            for file in debug_line.get_files():
                src_file = file.get_src_file()
                base_offset = file.get_base_offset()
                dl = HunkDebugLine(src_file, base_offset)
                for e in file.get_entries():
                    offset = e.get_offset()
                    src_line = e.get_src_line()
                    flags = e.get_flags()
                    hunk_src_line = src_line | (flags << 24)
                    dl.add_entry(offset, hunk_src_line)
                hunk_seg.setup_debug(dl)

    def create_image_from_load_seg_file(self, lsf):
        """create a BinImage from a HunkLoadSegFile object"""
        bi = BinImage(BIN_IMAGE_TYPE_HUNK)
        bi.set_file_data(lsf)
        segs = lsf.get_segments()
        for seg in segs:
            # what type of segment to we have?
            blk_id = seg.seg_blk.blk_id
            size = seg.size_longs * 4
            data = seg.seg_blk.data
            if blk_id == Hunk.HUNK_CODE:
                seg_type = SEGMENT_TYPE_CODE
            elif blk_id == Hunk.HUNK_DATA:
                seg_type = SEGMENT_TYPE_DATA
            elif blk_id == Hunk.HUNK_BSS:
                seg_type = SEGMENT_TYPE_BSS
            else:
                raise HunkParseError("Unknown Segment Type for BinImage: %d" % blk_id)
            # create seg
            bs = Segment(seg_type, size, data)
            bs.set_file_data(seg)
            bi.add_segment(bs)
        # add relocations if any
        bi_segs = bi.get_segments()
        for seg in bi_segs:
            # add relocations?
            hseg = seg.file_data
            reloc_blks = hseg.reloc_blks
            if reloc_blks is not None:
                self._add_hunk_relocs(reloc_blks, seg, bi_segs)
            # add symbol table
            symbol_blk = hseg.symbol_blk
            if symbol_blk is not None:
                self._add_hunk_symbols(symbol_blk, seg)
            # add debug infos
            debug_infos = hseg.debug_infos
            if debug_infos is not None:
                self._add_debug_infos(debug_infos, seg)

        return bi

    def _add_hunk_relocs(self, blks, seg, all_segs):
        """add relocations to a segment"""
        for blk in blks:
            if blk.blk_id not in (Hunk.HUNK_ABSRELOC32, Hunk.HUNK_RELOC32SHORT):
                raise HunkParseError("Invalid Relocations for BinImage: %d" % blk_id)
            relocs = blk.relocs
            for r in relocs:
                hunk_num = r[0]
                offsets = r[1]
                to_seg = all_segs[hunk_num]
                # create reloc for target segment or reuse one.
                rl = seg.get_reloc(to_seg)
                if rl == None:
                    rl = Relocations(to_seg)
                # add offsets
                for o in offsets:
                    r = Reloc(o)
                    rl.add_reloc(r)
                seg.add_reloc(to_seg, rl)

    def _add_hunk_symbols(self, blk, seg):
        """add symbols to segment"""
        syms = blk.symbols
        if len(syms) == 0:
            return
        st = SymbolTable()
        seg.set_symtab(st)
        for sym in syms:
            name = sym[0]
            offset = sym[1]
            symbol = Symbol(offset, name)
            st.add_symbol(symbol)

    def _add_debug_infos(self, debug_infos, seg):
        dl = DebugLine()
        seg.set_debug_line(dl)
        for debug_info in debug_infos:
            # add source line infos
            if isinstance(debug_info, HunkDebugLine):
                src_file = debug_info.src_file
                # abs path?
                pos = src_file.rfind("/")
                if pos != -1:
                    dir_name = src_file[:pos]
                    src_file = src_file[pos + 1 :]
                else:
                    dir_name = ""
                base_offset = debug_info.base_offset
                df = DebugLineFile(src_file, dir_name, base_offset)
                dl.add_file(df)
                for entry in debug_info.get_entries():
                    off = entry.offset
                    src_line = entry.src_line & 0xFFFFFF
                    flags = (entry.src_line & 0xFF000000) >> 24
                    e = DebugLineEntry(off, src_line, flags)
                    df.add_entry(e)


# mini test
if __name__ == "__main__":
    import sys

    bf = BinFmtHunk()
    for a in sys.argv[1:]:
        if bf.is_image(a):
            print("loading", a)
            bi = bf.load_image(a)
            print(bi)
            bf.save_image("a.out", bi)
        else:
            print("NO HUNK:", a)
