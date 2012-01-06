import os
import os.path
from ADFSDir import ADFSDir
from ADFSFile import ADFSFile

class Imager:
  # ----- unpack -----
  
  def unpack(self, volume, out_path):
    path = os.path.abspath(out_path)
    # check for volume path
    vol_name = volume.name
    vol_path = os.path.join(vol_name)
    if os.path.exists(vol_path):
      raise IOError("Unpack directory already exists: "+vol_path)
    # check for meta file
    meta_path = vol_path + ".xdfmeta"
    if os.path.exists(meta_path):
      raise IOError("Unpack meta file already exists:"+meta_path)
    # create volume path
    os.mkdir(vol_path)
    self.unpack_root(volume, vol_path)
    
  def unpack_root(self, volume, vol_path):
    for node in volume.root_dir.entries:
      self.unpack_node(node, vol_path)
    
  def unpack_node(self, node, path):
    name = node.name.name
    # sub dir
    if isinstance(node, ADFSDir):
      sub_dir = os.path.join(path, name)
      os.mkdir(sub_dir)
      for sub_node in node.entries:
        self.unpack_node(sub_node, sub_dir)
    # file
    elif isinstance(node, ADFSFile):
      data = node.get_file_data()
      file_path = os.path.join(path, name)
      fh = open(file_path, "wb")
      fh.write(data)
      fh.close()
  
  # ----- pack -----
  
  def pack(self, in_path, volume):
    blkdev = self.pack_create_blkdev(in_path)
    volume = self.pack_create_volume(in_path)
    self.pack_root(in_path, volume)
    
  def pack_create_blkdev(self, in_path, blkdev):
    blkdev.create()
    
  def pack_create_volume(self, in_path, volume):
    if in_path == None or in_path == "":
      raise IOError("Invalid pack input path!")
    # remove trailing slash
    if in_path[-1] == '/':
      in_path = in_path[:-1]
    name = os.path.basename(in_path)
    volume.create(name)
  
  def pack_root(self, in_path, volume):
    path = os.path.abspath(in_path)
    if not os.path.exists(path):
      raise IOError("Pack directory does not exist: "+path)
    self.pack_dir(path, volume.root_dir)
      
  def pack_dir(self, in_path, parent_node):
    for name in os.listdir(in_path):
      path = os.path.join(in_path, name)
      # sub dir
      if os.path.isdir(path):
        node = parent_node.create_dir(name)
        self.pack_dir(path, node)
      # file
      elif os.path.isfile(path):
        fh = open(path, "rb")
        data = fh.read()
        fh.close()
        node = parent_node.create_file(name, data)
        