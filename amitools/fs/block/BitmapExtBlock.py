from Block import Block

class BitmapExtBlock(Block):
  def __init__(self, blkdev, blk_num):
    Block.__init__(self, blkdev, blk_num)
  
  def set(self, data):
    self._set_data(data)
    self._read()
  
  def read(self):
    self._read_data()
    self._read()
  
  def _read(self):
    # read bitmap blk ptrs
    self.bitmap_ptrs = []
    for i in xrange(self.blkdev.block_longs-1):
      bm_blk = self._get_long(i)
      if bm_blk == 0:
        break
      self.bitmap_ptrs.append(bm_blk)
    
    self.bitmap_ext_blk = self._get_long(-1)
    
    self.valid = True
    return True
  
  def create(self):
    self.bitmap_ptrs = []
    for i in xrange(self.blkdev.block_longs-1):
      self.bitmap_ptrs.append(0)
    self.bitmap_ext_blk = 0
    self.valid = True
    return True
    
  def write(self):
    for i in xrange(self.blkdev.block_longs-1):
      self._put_long(i, self.bitmap_ptrs[i])
    self._put_long(-1, self.bitmap_ext_blk)
    Block.write(self)
    
  def dump(self):
    Block.dump(self,"Bitmap")
    print " bmp ptrs:  %s" % self.bitmap_ptrs
    print " bmp ext:   %d" % self.bitmap_ext_blk
  