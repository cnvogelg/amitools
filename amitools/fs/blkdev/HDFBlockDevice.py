from BlockDevice import BlockDevice
from DiskGeometry import DiskGeometry
import os.path
import os

class HDFBlockDevice(BlockDevice):
  def __init__(self, hdf_file, read_only=False):
    BlockDevice.__init__(self, read_only)
    self.hdf_file = hdf_file   
    self.dirty = False
    self.fh = None

  def create(self, size_str=None, geo=None, reserved=2):
    if self.read_only:
      raise IOError("HDF creation not allowed in read-only mode!")    
    # determine geometry from size or chs
    if geo ==None:
      geo = DiskGeometry()
      if size_str == None:
        raise IOError("No HDF disk geometry or size given!")      
      ok = geo.parse_size_str(size_str)
      if not ok:
        ok = geo.parse_chs_str(size_str)
        if not ok:
          raise IOError("Invalid HDF disk geometry or size given: "+size_str)
    self._set_geometry(geo.cyls, geo.heads, geo.secs, reserved=reserved)
    # create empty file
    self.fh = file(self.hdf_file,"wb")
    blk = '\0' * self.block_bytes
    for i in xrange(self.num_blocks):
      self.fh.write(blk)

  def open(self, guess_algo=None, block_bytes=512):
    # get size
    size = os.path.getsize(self.hdf_file)
    if size == 0:
      raise IOError("Empty HDF detected!")
    
    # guess disk geometry
    geo = DiskGeometry()
    if geo.guess_for_size(size, approx=False, algo=guess_algo) == None:
      raise IOError("Can't detect HDF disk geometry!")
    self._set_geometry(geo.cyls, geo.heads, geo.secs)
    
    # open adf file 
    if self.read_only:
      flags = "rb"
    else:
      flags = "r+b"
    self.fh = file(self.hdf_file, flags)
      
  def flush(self):
    pass
        
  def close(self):
    if self.fh != None:
      self.fh.close()
      self.fh = None

  def read_block(self, blk_num):
    if blk_num >= self.num_blocks:
      raise ValueError("Invalid HDF block num: got %d but max is %d" % (blk_num, self.num_blocks))
    off = self._blk_to_offset(blk_num)
    self.fh.seek(off, os.SEEK_SET)
    return self.fh.read(self.block_bytes)
  
  def write_block(self, blk_num, data):
    if self.read_only:
      raise IOError("HDF File is read-only!")
    if blk_num >= self.num_blocks:
      raise ValueError("Invalid HDF block num: got %d but max is %d" % (blk_num, self.num_blocks))
    if len(data) != self.block_bytes:
      raise ValueError("Invalid HDF block size written: got %d but size is %d" % (len(data), self.block_bytes))
    off = self._blk_to_offset(blk_num)
    self.fh.seek(off, os.SEEK_SET)
    self.fh.write(data)
    self.dirty = True
