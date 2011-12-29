from Block import Block

class RootBlock(Block):
  def __init__(self, blkdev, blk_num):
    Block.__init__(self, blkdev, blk_num, is_type=Block.T_SHORT, is_sub_type=Block.ST_ROOT)
  
  def read(self):
    Block.read(self)
    if not self.valid:
      return False
    
    # name hash
    self.hash_size = self._get_long(3)
    self.hash_table = []
    for i in xrange(self.hash_size):
      self.hash_table.append(self._get_long(6+i))
    
    # bitmap
    self.bitmap_flag = self._get_long(-50)
    self.bitmap_ptrs = []
    for i in xrange(25):
      bm_blk = self._get_long(-49+i)
      if bm_blk == 0:
        break
      self.bitmap_ptrs.append(bm_blk)
    self.bitmap_ext_blk = self._get_long(-24)
    
    # timestamps
    self.mod_ts = self._get_timestamp(-23)
    self.disk_ts = self._get_timestamp(-10)
    self.create_ts = self._get_timestamp(-7)
    
    # name
    self.name = self._get_bstr(-20, 30)
    
    # check validity
    self.valid = (self.bitmap_flag == 0xffffffff)
    return self.valid
  
  def dump(self):
    Block.dump(self, "Root")
    print " hash size: %d" % self.hash_size
    print " hash table:%s" % self.hash_table
    print " bmp flag:  0x%08x" % self.bitmap_flag
    print " bmp ptrs:  %s" % self.bitmap_ptrs
    print " bmp ext:   %d" % self.bitmap_ext_blk
    print " mod_ts:    %s" % self.mod_ts
    print " disk_ts:   %s" % self.disk_ts
    print " create_ts: %s" % self.create_ts
    print " disk name: %s" % self.name
     