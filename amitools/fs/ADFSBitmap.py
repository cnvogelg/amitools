import struct
from BitmapBlock import BitmapBlock
from BitmapExtBlock import BitmapExtBlock

class ADFSBitmap:
  def __init__(self, root_blk):
    self.root_blk = root_blk
    self.ext_blks = []
    self.bitmap_blks = None
    self.valid = False
    self.bitmap_data = None
    self.bitmap_blk_bytes = root_blk.blkdev.block_bytes - 4
    self.blkdev = self.root_blk.blkdev
  
  def read(self):
    self.bitmap_blks = []
    self.bitmap_data = ""
    
    # get bitmap blocks from root block
    blocks = self.root_blk.bitmap_ptrs
    for blk in blocks:
      bm = BitmapBlock(self.blkdev, blk)
      bm.read()
      if not bm.valid:
        return False
      self.bitmap_blks.append(bm)
      self.bitmap_data += bm.get_bitmap_data()
      
    # now check extended bitmap blocks
    ext_blk = self.root_blk.bitmap_ext_blk
    while ext_blk != 0:
      bm_ext = BitmapExtBlock(self.blkdev, ext_blk)
      bm_ext.read()
      if not bm_ext.valid:
        return False
      self.ext_blks.append(bm_ext)
      blocks = bm_ext.bitmap_ptrs
      for blk in blocks:
        bm = BitmapBlock(self.blkdev, blk)
        bm.read()
        if not bm.valid:
          return False
        self.bitmap_data += bm.get_bitmap_data()
        self.bitmap_blks.append(bm)

    # check bitmap data
    num_bm_blks = len(self.bitmap_blks)
    num_bytes = self.bitmap_blk_bytes * num_bm_blks
    if num_bytes != len(self.bitmap_data):
      return False
    
    self.valid = True
    return self.valid

  def get_bit(self, off):
    if off < self.blkdev.reserved or off >= self.blkdev.num_blocks:
      return None
    off = (off - self.blkdev.reserved)
    long_off = off / 32
    bit_off = off % 32
    val = struct.unpack_from(">I", self.bitmap_data, long_off * 4)[0]
    mask = 1 << bit_off
    return (val & mask) == mask

  def dump(self):
    print "Bitmap:"
    print "  ext: ",self.ext_blks
    print "  blks:",len(self.bitmap_blks)
    print "  bits:",len(self.bitmap_data) * 8,self.blkdev.num_blocks
    line = ""
    blk = 0
    blk_cyl = self.blkdev.sectors * self.blkdev.heads
    for i in xrange(self.blkdev.num_blocks):
      if i < self.blkdev.reserved:
        line += "."
      else:
        b = self.get_bit(i)
        if b:
          line += "1"
        else:
          line += "0"
      if i % self.blkdev.sectors == self.blkdev.sectors - 1:
        line += " "
      if i % blk_cyl == blk_cyl - 1:
        print "%8d: %s" % (blk,line)
        blk += blk_cyl
        line = ""
    