from BootBlock import BootBlock
from RootBlock import RootBlock
from ADFSDir import ADFSDir
from ADFSBitmap import ADFSBitmap

class ADFSVolume:
  def __init__(self, blkdev):
    self.blkdev = blkdev
    self.boot = None
    self.root = None
    self.root_dir = None
    self.bitmap = None
    self.valid = False
    self.error = None
    
  def open(self):
    self.blkdev.open()
    # read boot block
    self.boot = BootBlock(self.blkdev)
    self.boot.read()
    # valid root block?
    if self.boot.valid:
      # read root 
      self.root = RootBlock(self.blkdev, self.boot.root_blk)
      self.root.read()
      if self.root.valid:
        # create root dir
        self.root_dir = ADFSDir(self.root)
        dir_ok = self.root_dir.read()
        if not dir_ok:
          self.error = "Invalid RootDir"
        # create bitmap
        self.bitmap = ADFSBitmap(self.root)
        bm_ok = self.bitmap.read()
        if not bm_ok:
          self.error = "Invalid Bitmap"

        self.valid = dir_ok and bm_ok
      else:
        self.error = "Invalid RootBlock"
    else:
      self.error = "Invalid BootBlock"
    return self.valid
    
  def close(self):
    self.blkdev.close()
