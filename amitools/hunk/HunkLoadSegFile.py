from __future__ import print_function

from HunkBlockFile import *


class HunkSegment:
  """holds a code, data, or bss hunk/segment"""
  def __init__(self):
    self.blocks = None
    self.seg_blk = None
    self.symbol_blk = None
    self.reloc_blk = None
    self.debug_blks = None
    self.size_longs = 0

  def __repr__(self):
    return "[seg=%s,symbol=%s,reloc=%s,debug=%s,size=%d]" % \
      (self._blk_str(self.seg_blk),
       self._blk_str(self.symbol_blk),
       self._blk_str(self.reloc_blk),
       self._blk_str_list(self.debug_blks),
       self.size)

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
      elif blk_id in (HUNK_ABSRELOC32, HUNK_RELOC32SHORT):
        if self.reloc_blk is None:
          self.reloc_blk = blk
        else:
          raise HunkParseError("duplicate relocs in hunk")
      else:
        raise HunkParseError("invalid hunk block")


class HunkLoadSegFile:
  """manage a LoadSeg() hunk file starting with HUNK_HEADER"""
  def __init__(self):
    self.hdr_blk = None
    self.segments = []

  def get_segments(self):
    return self.segments

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
        if blk_id not in loadseg_valid_begin_hunks and \
           blk_id not in loadseg_valid_extra_hunks:
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
        off+=1
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
    for i in xrange(n):
      self.segments[i].size_longs = hdr_blk.hunk_table[i]


# mini test
if __name__ == '__main__':
  import sys
  for a in sys.argv[1:]:
    bf = HunkBlockFile(isLoadSeg=True)
    bf.read_path(a)
    print(bf.get_block_type_names())
    lsf = HunkLoadSegFile()
    lsf.parse_block_file(bf)
    print(lsf.get_segments())
