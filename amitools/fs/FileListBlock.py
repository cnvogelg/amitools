from Block import Block

class FileListBlock(Block):
  def __init__(self, blkdev, blk_num):
    Block.__init__(self, blkdev, blk_num, is_type=Block.T_LIST, is_sub_type=Block.ST_FILE)
  
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
    
    # FileList fields
    self.own_key = self._get_long(1)
    self.block_count = self._get_long(2)
    
    self.data_blocks = []
    for i in xrange(self.block_count):
      self.data_blocks.append(self._get_long(-51-i))
    
    self.parent = self._get_long(-3)
    self.extension = self._get_long(-2)

    self.valid = (self.own_key == self.blk_num)
    return self.valid
  
  def dump(self):
    Block.dump(self,"FileList")
    print " own_key:    %d" % self.own_key
    print " blk_cnt:    %d" % self.block_count
    print " data blks:  %s" % self.data_blocks
    print " parent:     %d" % self.parent
    print " extension:  %d" % self.extension
  