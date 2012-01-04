import time
from Block import Block
from ..TimeStamp import *

class RootBlock(Block):
  def __init__(self, blkdev, blk_num):
    Block.__init__(self, blkdev, blk_num, is_type=Block.T_SHORT, is_sub_type=Block.ST_ROOT)
  
  def create(self, name, create_time=None, disk_time=None, mod_time=None):
    # init fresh hash table
    self.hash_size = self.blkdev.block_longs - 56
    self.hash_table = []
    for i in xrange(self.hash_size):
      self.hash_table.append(0)
    
    # timestamps
    if create_time == None:
      create_time = time.mktime(time.localtime())
    if disk_time == None:
      disk_time = create_time
    if mod_time == None:
      mod_time = create_time
    self.mod_ts = ts_create_from_secs(mod_time)
    self.disk_ts = ts_create_from_secs(disk_time)
    self.create_ts = ts_create_from_secs(create_time)
    
    # name
    self.name = name
    
    # bitmap: blank 
    self.bitmap_flag = 0xffffffff
    self.bitmap_ptrs = []
    for i in xrange(25):
      self.bitmap_ptrs.append(0)
    self.bitmap_ext_blk = 0
  
  def write(self):
    self._create_data()
    
    # hash table
    self._put_long(3, self.hash_size)
    for i in xrange(self.hash_size):
      self._put_long(6+i, self.hash_table[i])
    
    # bitmap
    self._put_long(-50, self.bitmap_flag)
    for i in xrange(25):
      self._put_long(-49+i, self.bitmap_ptrs[i])
    self._put_long(-24, self.bitmap_ext_blk)
    
    # timestamps
    self._put_timestamp(-23, self.mod_ts)
    self._put_timestamp(-10, self.disk_ts)
    self._put_timestamp(-7, self.create_ts)
    
    # name
    self._put_bstr(-20, 30, self.name)
    
    Block.write(self)
  
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
     