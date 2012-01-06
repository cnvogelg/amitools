from block.BootBlock import BootBlock
from block.RootBlock import RootBlock
from ADFSDir import ADFSDir
from ADFSBitmap import ADFSBitmap
from FileName import FileName
from FSError import *

class ADFSVolume:
  def __init__(self, blkdev):
    self.blkdev = blkdev
    
    self.boot = None
    self.root = None
    self.root_dir = None
    self.bitmap = None
    
    self.valid = False
    self.is_ffs = None
    self.name = None
    
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
        self.name = self.root.name
        # create root dir
        self.root_dir = ADFSDir(self, None)
        self.root_dir.set_root(self.root)
        self.root_dir.read()
        # create bitmap
        self.bitmap = ADFSBitmap(self.root)
        self.bitmap.read()
        self.valid = True
      else:
        raise FSError(INVALID_ROOT_BLOCK, block=self.root)
    else:
      raise FSError(INVALID_BOOT_BLOCK, block=self.boot)
  
  def create(self, name, create_time=None, dos_type=BootBlock.DOS0, boot_code=None):
    # create a boot block
    self.boot = BootBlock(self.blkdev)
    self.boot.create()
    self.boot.write()
    # create a root block
    self.root = RootBlock(self.blkdev, self.boot.calc_root_blk)
    self.root.create(name, create_time)
    self.name = name
    # create bitmap
    self.bitmap = ADFSBitmap(self.root)
    self.bitmap.create()
    self.bitmap.write() # writes root block, too
    # create empty root dir
    self.root_dir = ADFSDir(self, None)
    self.root_dir.set_root(self.root)
    self.root_dir.read()
    # all ok
    self.valid = True
  
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
  
  def get_create_path_name(self, path_name, suggest_name=None):
    """get a parent node and path name for creation
       return: parent_node_or_none, file_name_or_none
    """
    if path_name == None or path_name == "":
      return self.root_dir, suggest_name
    else:
      # try to get path_name as a directory
      node = self.get_dir_path_name(path_name)
      if node != None:
        return node, suggest_name
      # is a file name appended?
      pos = path_name.rfind('/')
      if pos != -1:
        dir_name = path_name[0:pos]
        file_name = path_name[pos+1:]
        if len(file_name) == 0:
          file_name = suggest_name
        node = vol.get_dir_path_name(dir_name)
        return node, file_name
      else:
        # its a file name
        return self.root_dir, path_name
  
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