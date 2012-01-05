import time
from Block import Block
from ..ProtectFlags import ProtectFlags
from ..TimeStamp import *

class FileHeaderBlock(Block):
  def __init__(self, blkdev, blk_num):
    Block.__init__(self, blkdev, blk_num, is_type=Block.T_SHORT, is_sub_type=Block.ST_FILE)
  
  def set(self, data):
    self._set_data(data)
    self._read()
  
  def read(self):
    self._read_data()
    self._read()
  
  def _read(self):
    Block.read(self)
    if not self.valid:
      return False
    
    # FileHeader fields
    self.own_key = self._get_long(1)
    self.block_count = self._get_long(2)
    self.first_data = self._get_long(4)
    
    self.data_blocks = []
    for i in xrange(self.block_count):
      self.data_blocks.append(self._get_long(-51-i))
    
    self.protect = self._get_long(-48)
    self.protect_flags = ProtectFlags(self.protect)
    self.byte_size = self._get_long(-47)
    self.comment = self._get_bstr(-46, 79)
    self.mod_ts = self._get_timestamp(-23)
    self.name = self._get_bstr(-20, 30)
    self.hash_chain = self._get_long(-4)
    self.parent = self._get_long(-3)
    self.extension = self._get_long(-2)

    self.valid = (self.own_key == self.blk_num)
    return self.valid
  
  def write(self):
    Block._create_data(self)
    self._put_long(1, self.own_key)
    self._put_long(2, self.block_count)
    self._put_long(4, self.first_data)
    
    # data blocks
    for i in xrange(len(self.data_blocks)):
      self._put_long(-51-i, self.data_blocks[i])
    
    self._put_long(-48, self.protect)
    self._put_long(-47, self.byte_size)
    self._put_bstr(-46, 79, self.comment)
    self._put_timestamp(-23, self.mod_ts)
    self._put_bstr(-20, 30, self.name)
    self._put_long(-4, self.hash_chain)
    self._put_long(-3, self.parent)
    self._put_long(-2, self.extension)
    Block.write(self)
  
  def create(self, parent, name, data_blocks, extension, byte_size=0, protect=0, comment=None, mod_ts=0, hash_chain=0):
    Block.create(self)
    self.own_key = self.blk_num
    n = len(data_blocks)
    self.block_count = n
    if n == 0:
      self.first_data = 0
    else:
      self.first_data = data_blocks[0]
    
    self.data_blocks = data_blocks
    self.protect = protect
    self.protect_flags = ProtectFlags(self.protect)
    self.byte_size = byte_size
    if comment == None:
      self.comment = ''
    else:
      self.comment = comment
    self.mod_ts = mod_ts
    self.name = name
    self.hash_chain = hash_chain
    self.parent = parent
    self.extension = extension
    self.valid = True
    return True
    
  def dump(self):
    Block.dump(self,"FileHeader")
    print " own_key:    %d" % self.own_key
    print " blk_cnt:    %d" % self.block_count
    print " first_data: %d" % self.first_data
    print " data blks:  %s" % self.data_blocks
    print " protect:    0x%x" % self.protect
    print " byte_size:  %d" % self.byte_size
    print " comment:    '%s'" % self.comment
    print " mod_ts:     %s" % self.mod_ts
    print " name:       '%s'" % self.name
    print " hash_chain: %d" % self.hash_chain
    print " parent:     %d" % self.parent
    print " extension:  %d" % self.extension
  