import struct
import ctypes

from BitmapBlock import BitmapBlock
from BitmapExtBlock import BitmapExtBlock

class ADFSBitmap:
  def __init__(self, root_blk):
    self.root_blk = root_blk
    self.blkdev = self.root_blk.blkdev
    # state
    self.ext_blks = []
    self.bitmap_blks = []
    self.bitmap_data = None
    self.valid = False
    # bitmap block entries
    self.bitmap_blk_bytes = root_blk.blkdev.block_bytes - 4
    self.bitmap_blk_longs = root_blk.blkdev.block_longs - 1
    # calc size of bitmap
    self.bitmap_bits = self.blkdev.num_blocks - self.blkdev.reserved
    self.bitmap_longs = self.bitmap_bits / 32
    self.bitmap_bytes = self.bitmap_bits / 8
    # number of blocks required for bitmap (and bytes consumed there)
    self.bitmap_num_blks = (self.bitmap_longs + self.bitmap_blk_longs - 1) / self.bitmap_blk_longs
    self.bitmap_all_blk_bytes = self.bitmap_num_blks * self.bitmap_blk_bytes
    # blocks stored in root and in every ext block
    self.num_blks_in_root = len(self.root_blk.bitmap_ptrs)
    self.num_blks_in_ext = self.blkdev.block_longs - 1
    # number of ext blocks required
    self.num_ext = (self.bitmap_num_blks - self.num_blks_in_root + self.num_blks_in_ext - 1) / (self.num_blks_in_ext) 
  
  def create(self):
    # create data and preset with 0xff
    self.bitmap_data = ctypes.create_string_buffer(self.bitmap_all_blk_bytes)
    for i in xrange(self.bitmap_all_blk_bytes):
      self.bitmap_data[i] = chr(0xff)

    # clear bit for root block
    blk_pos = self.root_blk.blk_num
    self.clr_bit(blk_pos)
    blk_pos += 1
    
    # create ext blocks
    for i in xrange(self.num_ext):
      bm_ext = BitmapExtBlock(self.blkdev, blk_pos)
      bm_ext.create()
      self.clr_bit(blk_pos)
      blk_pos += 1
      self.ext_blks.append(bm_ext)
      
    # create bitmap blocks
    for i in xrange(self.bitmap_num_blks):
      bm = BitmapBlock(self.blkdev, blk_pos)
      bm.create()
      self.clr_bit(blk_pos)
      blk_pos += 1
      self.bitmap_blks.append(bm)
      
    # set pointers to ext blocks
    if self.num_ext > 0:
      self.root_blk.bitmap_ext_blk = self.ext_blks[0].blk_num
      for i in xrange(self.num_ext)-1:
        bm_ext = self.ext_blks[i]
        bm_ext_next = self.ext_blks[i+1]
        bm_ext.bitmap_ext_blk = bm_ext_next.blk_num
    
    # set pointers to bitmap blocks
    cur_ext_index = 0
    cur_ext_pos = 0
    for i in xrange(self.bitmap_num_blks):
      blk_num = self.bitmap_blks[i].blk_num
      if i < self.num_blks_in_root:
        # pointers in root block
        self.root_blk.bitmap_ptrs[i] = blk_num
      else:
        # pointers in ext block
        self.ext_blks[cur_ext_index].bitmap_ptrs[cur_ext_pos] = blk_num
        cur_ext_pos += 1
        if cur_ext_pos == self.num_blks_in_ext:
          cur_ext_pos = 0
          cur_ext_index += 1
    
    self.valid = True
    return True
  
  def write(self):
    # write root block
    self.root_blk.write()
    # write ext blocks
    for ext_blk in self.ext_blks:
      ext_blk.write()
    # write bitmap blocks
    off = 0
    for blk in self.bitmap_blks:
      blk.set_bitmap_data(self.bitmap_data[off:off+self.bitmap_blk_bytes])
      blk.write()
      off += self.bitmap_blk_bytes
  
  def read(self):
    self.bitmap_blks = []
    bitmap_data = ""
    
    # get bitmap blocks from root block
    blocks = self.root_blk.bitmap_ptrs
    for blk in blocks:
      bm = BitmapBlock(self.blkdev, blk)
      bm.read()
      if not bm.valid:
        return False
      self.bitmap_blks.append(bm)
      bitmap_data += bm.get_bitmap_data()
      
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
        bitmap_data += bm.get_bitmap_data()
        self.bitmap_blks.append(bm)

    # check bitmap data
    num_bm_blks = len(self.bitmap_blks)
    num_bytes = self.bitmap_blk_bytes * num_bm_blks
    if num_bytes != len(bitmap_data):
      return False
    if num_bm_blks != self.bitmap_num_blks:
      return False
  
    # create a modyfiable bitmap
    self.bitmap_data = ctypes.create_string_buffer(bitmap_data)
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

  def set_bit(self, off):
    if off < self.blkdev.reserved or off >= self.blkdev.num_blocks:
      return False
    off = (off - self.blkdev.reserved)
    long_off = off / 32
    bit_off = off % 32
    val = struct.unpack_from(">I", self.bitmap_data, long_off * 4)[0]
    mask = 1 << bit_off
    val = val | mask
    struct.pack_into(">I", self.bitmap_data, long_off * 4, val)
    return True
    
  def clr_bit(self, off):
    if off < self.blkdev.reserved or off >= self.blkdev.num_blocks:
      return False
    off = (off - self.blkdev.reserved)
    long_off = off / 32
    bit_off = off % 32
    val = struct.unpack_from(">I", self.bitmap_data, long_off * 4)[0]
    mask = 1 << bit_off
    val = val & ~mask
    struct.pack_into(">I", self.bitmap_data, long_off * 4, val)
    return True

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
    