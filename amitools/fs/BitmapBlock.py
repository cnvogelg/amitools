from Block import Block

class BitmapBlock(Block):
  def __init__(self, blkdev, blk_num):
    Block.__init__(self, blkdev, blk_num)
  
  def set(self, data):
    self._set_data(data)
    self._read()
  
  def read(self):
    self._read_data()
    self._read()
  
  def _read(self):
    Block.read(self, chk_loc=0)
    if not self.valid:
      return False
    self.valid = True
    return True
    
  def get_bitmap_data(self):
    return self.data[4:]
  
  def dump(self):
    Block.dump(self,"Bitmap")
  
