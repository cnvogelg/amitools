import os
from ADFBlockDevice import ADFBlockDevice
from HDFBlockDevice import HDFBlockDevice
from RawBlockDevice import RawBlockDevice

class BlkDevFactory:
  def create(self, img_file, read_only=False):
    # check access
    if not os.access(img_file, os.W_OK):
      read_only = True
    # check extension
    ext = img_file.lower()
    if ext.endswith('.adf'):
      return ADFBlockDevice(img_file, read_only)
    elif ext.endswith(".hdf"):
      return HDFBlockDevice(img_file, read_only)
    elif ext.endswith(".rdsk"):
      return RawBlockDevice(img_file, read_only)
    else:
      return None
    