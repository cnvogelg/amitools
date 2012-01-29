from BlockDevice import BlockDevice
import os.path
import os

class RawBlockDevice(BlockDevice):
  def __init__(self, raw_file, read_only=False):
    BlockDevice.__init__(self, read_only)
    self.raw_file = raw_file   
    self.fh = None

  def open(self, guess_algo=None, block_bytes=512):
    # get size
    size = os.path.getsize(self.raw_file)
    if size == 0:
      raise IOError("Empty RAW device detected!")
    
    # calc num blocks
    self.block_bytes = block_bytes
    self.num_blocks = size / block_bytes
    self.block_longs = self.block_bytes / 4
    
    # open raw file 
    if self.read_only:
      flags = "rb"
    else:
      flags = "r+b"
    self.fh = file(self.raw_file, flags)
      
  def flush(self):
    pass
        
  def close(self):
    if self.fh != None:
      self.fh.close()
      self.fh = None

  def read_block(self, blk_num):
    if blk_num >= self.num_blocks:
      raise ValueError("Invalid RAW block num: got %d but max is %d" % (blk_num, self.num_blocks))
    off = self._blk_to_offset(blk_num)
    self.fh.seek(off, os.SEEK_SET)
    return self.fh.read(self.block_bytes)
  
  def write_block(self, blk_num, data):
    if self.read_only:
      raise IOError("HDF File is read-only!")
    if blk_num >= self.num_blocks:
      raise ValueError("Invalid RAW block num: got %d but max is %d" % (blk_num, self.num_blocks))
    if len(data) != self.block_bytes:
      raise ValueError("Invalid RAW block size written: got %d but size is %d" % (len(data), self.block_bytes))
    off = self._blk_to_offset(blk_num)
    self.fh.seek(off, os.SEEK_SET)
    self.fh.write(data)
    self.dirty = True
