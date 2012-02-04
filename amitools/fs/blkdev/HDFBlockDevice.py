from BlockDevice import BlockDevice
from DiskGeometry import DiskGeometry
from ImageFile import ImageFile
import os.path
import os

class HDFBlockDevice(BlockDevice):
  def __init__(self, hdf_file, read_only=False, block_size=512):
    self.img_file = ImageFile(hdf_file, read_only, block_size)

  def create(self, size_str=None, geo=None, reserved=2):
    # determine geometry from size or chs
    if geo ==None:
      geo = DiskGeometry()
      if size_str == None:
        raise IOError("No HDF disk geometry or size given!")      
      ok = geo.parse_str(size_str)
      if not ok:
        raise IOError("Invalid HDF disk geometry or size given: "+size_str)
    self._set_geometry(geo.cyls, geo.heads, geo.secs, reserved=reserved)
    # create empty file
    self.img_file.create(geo.get_num_blocks())
    self.img_file.open()

  def open(self, guess_algo=None, block_bytes=512):
    self.img_file.open()
    # guess disk geometry
    size = self.img_file.size
    geo = DiskGeometry()
    if geo.guess_for_size(size, approx=False, algo=guess_algo) == None:
      raise IOError("Can't detect HDF disk geometry!")
    self._set_geometry(geo.cyls, geo.heads, geo.secs)
      
  def flush(self):
    pass
        
  def close(self):
    self.img_file.close()

  def read_block(self, blk_num):
    return self.img_file.read_blk(blk_num)
  
  def write_block(self, blk_num, data):
    return self.img_file.write_blk(blk_num, data)
