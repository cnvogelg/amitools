from BootBlock import BootBlock
from RootBlock import RootBlock
from ADFSDir import ADFSDir
from ADFSBitmap import ADFSBitmap
from FileName import FileName

class ADFSVolume:
  def __init__(self, blkdev):
    self.blkdev = blkdev
    
    self.boot = None
    self.root = None
    self.root_dir = None
    self.bitmap = None
    
    self.valid = False
    self.error = None
    self.is_ffs = None
    
  def open(self):
    # read boot block
    self.boot = BootBlock(self.blkdev)
    self.boot.read()
    # valid root block?
    if self.boot.valid:
      self.is_ffs = self.boot.dos_type > BootBlock.DOS0
      # read root 
      self.root = RootBlock(self.blkdev, self.boot.calc_root_blk)
      self.root.read()
      if self.root.valid:
        # create root dir
        self.root_dir = ADFSDir(self, self.root, is_vol=True)
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
  
  def create(self, name, create_time=None, dos_type=BootBlock.DOS0, boot_code=None):
    # create a boot block
    self.boot = BootBlock(self.blkdev)
    ok = self.boot.create()
    if not ok:
      return False
    self.boot.write()
    # create a root block
    self.root = RootBlock(self.blkdev, self.boot.calc_root_blk)
    self.root.create(name, create_time)
    # create bitmap
    self.bitmap = ADFSBitmap(self.root)
    self.bitmap.create()
    self.bitmap.write() # write root block, too
    # create empty root dir
    self.root_dir = ADFSDir(self, self.root, is_vol=True)
    self.root_dir.read()
    # all ok
    self.valid = True
    return True
  
  def close(self):
    pass

  def get_path_name(self, path_name, allow_file=True, allow_dir=True):
    if path_name == "" or path_name == "/":
      return self.root_dir
    pc = path_name.split("/")
    fn = []
    for path in pc:
      fn.append(FileName(path))
    return self.root_dir.get_path(fn, allow_file, allow_dir)

  def get_dir_path_name(self, path_name):
    return self.get_path_name(path_name, allow_file=False)
  
  def get_file_path_name(self, path_name):
    return self.get_path_name(path_name, allow_dir=False)
  
  def create_dir(self, path_name):
    pc = path_name.split("/")
    # no directory given
    if len(pc) == 0:
      return False
    # no parent dir found
    node = self.get_dir_path_name("/".join(pc[:-2]))
    if node == None:
      return False
    return node.create_dir(path_name)