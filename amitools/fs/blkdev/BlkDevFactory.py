from ADFBlockDevice import ADFBlockDevice
from HDFBlockDevice import HDFBlockDevice

class BlkDevFactory:
  def create(self, img_file, read_only=False):    
    ext = img_file.lower()
    if ext.endswith('.adf'):
      return ADFBlockDevice(img_file, read_only)
    elif ext.endswith(".hdf"):
      return HDFBlockDevice(img_file, read_only)
    else:
      return None
    