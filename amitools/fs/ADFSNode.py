from FileName import FileName

class ADFSNode:
  def __init__(self, volume):
    self.volume = volume
    self.blkdev = volume.blkdev
    self.block_bytes = self.blkdev.block_bytes
    self.block = None
    self.name = None
    self.valid = False
  
  def set_block(self, block):  
    self.block = block
    self.name = FileName(self.block.name)
    self.valid = True

  def get_file_name_str(self):
    return self.name.name
