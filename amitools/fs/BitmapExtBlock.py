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
    
  def get_bitmap_data(self):
    return self.data[4:]
  
  def dump(self):
    Block.dump(self,"Bitmap")
    print " bmp ptrs:  %s" % self.bitmap_ptrs
    print " bmp ext:   %d" % self.bitmap_ext_blk
  