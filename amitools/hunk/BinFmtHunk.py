from __future__ import print_function

from amitools.binfmt.BinImage import *
from HunkBlockFile import HunkBlockFile, HunkParseError
from HunkLoadSegFile import HunkLoadSegFile
import Hunk

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
      reloc_blk = hseg.reloc_blk
      if reloc_blk is not None:
        self.add_hunk_relocs(reloc_blk, seg, bi_segs)
      # add symbol table
      symbol_blk = hseg.symbol_blk
      if symbol_blk is not None:
        self.add_hunk_symbols(symbol_blk, seg)
    return bi

  def add_hunk_relocs(self, blk, seg, all_segs):
    """add relocations to a segment"""
    if blk.blk_id not in (Hunk.HUNK_ABSRELOC32, Hunk.HUNK_RELOC32SHORT):
      raise HunkParseError("Invalid Relocations for BinImage: %d" % blk_id)
    relocs = blk.relocs
    for r in relocs:
      hunk_num = r[0]
      offsets = r[1]
      to_seg = all_segs[hunk_num]
      # create reloc for target segment
      rl = Relocations(to_seg)
      # add offsets
      for o in offsets:
        r = Reloc(o)
        rl.add_reloc(r)
      seg.add_reloc(to_seg, rl)

  def add_hunk_symbols(self, blk, seg):
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


# mini test
if __name__ == '__main__':
  import sys
  bf = BinFmtHunk()
  for a in sys.argv[1:]:
    if bf.is_image(a):
      print("loading", a)
      bi = bf.load_image(a)
      print(bi)
    else:
      print("NO HUNK:", a)
