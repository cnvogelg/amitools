from BlockDevice import BlockDevice
import os.path
import os

class HDFBlockDevice(BlockDevice):
  def __init__(self, hdf_file, read_only=False):
    BlockDevice.__init__(self, read_only)
    self.hdf_file = hdf_file   
    self.dirty = False

  def create(self, cylinders, heads, sectors, reserved=2):
    self.read_only=False
    self.fh = file(self.hdf_file,"wb")
    self._set_geometry(0, cylinders-1, heads, sectors, reserved)
    # create empty file
    blk = '\0' * self.block_bytes
    for i in xrange(self.num_blocks):
      self.fh.write(blk)

  def guess_geometry1(self, size, block_bytes=512):
    mb = size / 1024
    secs = 63
    if mb <= 504 * 1024:
      heads = 16
    elif mb <= 1008 * 1024:
      heads = 32
    elif mb <= 2016 * 1024:
      heads = 64
    elif mb <= 4032 * 1024:
      heads = 128
    else:
      heads = 256
    cyls = (size / block_bytes) / (secs * heads)
    geo_size = cyls * secs * heads * block_bytes
    if geo_size == size:
      return cyls,heads,secs
    else:
      return None

  def guess_geometry2(self, size, block_bytes=512):
    heads = 1
    secs = 32
    cyls = (size / block_bytes) / (secs * heads)
    geo_size = cyls * secs * heads * block_bytes
    if geo_size == size:
      return cyls,heads,secs
    else:
      return None

  def open(self, block_bytes=512):
    # get size
    size = os.path.getsize(self.hdf_file)
    if size == 0:
      raise IOError("Empty HDF detected!")
    
    chs = self.guess_geometry1(size)
    if chs == None:
      chs = self.guess_geometry2(size)
      if chs == None:
        raise IOError("Can't detect HDF geometry!")
      
    self._set_geometry(0, chs[0]-1, chs[1], chs[2])
    
    # open adf file 
    if self.read_only:
      flags = "rb"
    else:
      flags = "r+b"
    self.fh = file(self.hdf_file, flags)
      
  def flush(self):
    pass
        
  def close(self):
    self.fh.close()

  def read_block(self, blk_num):
    if blk_num >= self.num_blocks:
      raise ValueError("Invalid ADF block num: got %d but max is %d" % (blk_num, self.num_blocks))
    off = self._blk_to_offset(blk_num)
    self.fh.seek(off, os.SEEK_SET)
    return self.fh.read(self.block_bytes)
  
  def write_block(self, blk_num, data):
    if self.read_only:
      raise IOError("ADF File is read-only!")
    if blk_num >= self.num_blocks:
      raise ValueError("Invalid ADF block num: got %d but max is %d" % (blk_num, self.num_blocks))
    if len(data) != self.block_bytes:
      raise ValueError("Invalid ADF block size written: got %d but size is %d" % (len(data), self.block_bytes))
    off = self._blk_to_offset(blk_num)
    self.fh.seek(off, os.SEEK_SET)
    self.fh.write(data)
    self.dirty = True
