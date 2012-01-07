from block.BootBlock import BootBlock
from block.RootBlock import RootBlock
from ADFSVolDir import ADFSVolDir
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
    self.is_intl = None
    self.is_dircache = None
    self.name = None
    
  def open(self):
    # read boot block
    self.boot = BootBlock(self.blkdev)
    self.boot.read()
    # valid root block?
    if self.boot.valid:
      # get fs flags
      self.is_ffs = self.boot.is_ffs()
      self.is_intl = self.boot.is_intl()
      self.is_dircache = self.boot.is_dircache()
      # read root 
      self.root = RootBlock(self.blkdev, self.boot.calc_root_blk)
      self.root.read()
      if self.root.valid:
        self.name = self.root.name
        # create root dir
        self.root_dir = ADFSVolDir(self, self.root)
        self.root_dir.read()
        # create bitmap
        self.bitmap = ADFSBitmap(self.root)
        self.bitmap.read()
        self.valid = True
      else:
        raise FSError(INVALID_ROOT_BLOCK, block=self.root)
    else:
      raise FSError(INVALID_BOOT_BLOCK, block=self.boot)
  
  def create(self, name, create_time=None, dos_type=None, boot_code=None, is_ffs=False, is_intl=False, is_dircache=False):
    # determine dos_type
    if dos_type == None:
      dos_type = BootBlock.DOS0
      if is_ffs:
        dos_type |= BootBlock.DOS_MASK_FFS
      if is_dircache:
        dos_type |= BootBlock.DOS_MASK_DIRCACHE
      elif is_intl:
        dos_type |= BootBlock.DOS_MASK_INTL
    # create a boot block
    self.boot = BootBlock(self.blkdev, )
    self.boot.create(dos_type=dos_type, boot_code=boot_code)
    self.is_ffs = self.boot.is_ffs()
    self.is_intl = self.boot.is_intl()
    self.is_dircache = self.boot.is_dircache()
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
    self.root_dir = ADFSVolDir(self, self.root)
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
        node = self.get_dir_path_name(dir_name)
        return node, file_name
      else:
        # its a file name
        return self.root_dir, path_name
  
  # ----- convenience API -----
  
  def create_dir(self, ami_path):
    pc = ami_path.split("/")
    # no directory given
    if len(pc) == 0:
      raise FSError(INVALID_PARENT_DIRECTORY, file_name=ami_path)
    # no parent dir found
    node = self.get_dir_path_name("/".join(pc[:-1]))
    if node == None:
      raise FSError(INVALID_PARENT_DIRECTORY, file_name=ami_path)
    node.create_dir(pc[-1])
    
  def write_file(self, data, ami_path=None, file_name=None, cache=False):
    parent_node, file_name = self.get_create_path_name(ami_path, file_name)
    if parent_node == None:
      raise FSError(INVALID_PARENT_DIRECTORY, file_name=ami_path)
    if file_name == None:
      raise FSError(INVALID_FILE_NAME, file_name=file_name)
    # create file
    node = parent_node.create_file(file_name, data)
    if not cache:
      node.flush()
  
  def read_file(self, ami_path, cache=False):
    node = self.get_file_path_name(ami_path)
    if node == None:
      raise FSError(FILE_NOT_FOUND, file_name=ami_path)
    data = node.get_file_data()
    if not cache:
      node.flush()
    return data
  
  def delete(self, ami_path, wipe=False, all=False):
    node = self.get_path_name(ami_path)
    if node == None:
      raise FSError(INVALID_FILE_NAME, file_name=ami_path)
    node.delete(wipe=wipe, all=all)
