from Block import Block

class FileDataBlock(Block):
  def __init__(self, blkdev, blk_num):
    Block.__init__(self, blkdev, blk_num, is_type=Block.T_DATA)
  
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
    
    # FileData fields
    self.hdr_key = self._get_long(1)
    self.seq_num = self._get_long(2)
    self.data_size = self._get_long(3)
    self.next_data = self._get_long(4)
    
    self.valid = True
    return self.valid
    
  def get_block_data(self):
    return self.data[24:24+self.data_size]
  
  def dump(self):
    Block.dump(self,"FileData")
    print " hdr_key:    %d" % self.hdr_key
    print " seq_num:    %d" % self.seq_num
    print " data size:  %d" % self.data_size
    print " next_data:  %d" % self.next_data
  
