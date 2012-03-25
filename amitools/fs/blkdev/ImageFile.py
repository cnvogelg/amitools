import os
import stat
import amitools.util.BlkDevTools as BlkDevTools

class ImageFile:
  def __init__(self, file_name, read_only=False, block_bytes=512):
    self.file_name = file_name
    self.read_only = read_only
    self.block_bytes = block_bytes
    self.fh = None
    self.size = 0
    self.num_blocks = 0
    
  def open(self):
    # is readable?
    if not os.access(self.file_name, os.R_OK):
      raise IOError("Can't read from image file")
    # is writeable?
    if not os.access(self.file_name, os.W_OK):
      self.read_only = True
    # is it a block/char device?
    st = os.stat(self.file_name)
    mode = st.st_mode
    if stat.S_ISBLK(mode) or stat.S_ISCHR(mode):
      self.size = BlkDevTools.getblkdevsize(self.file_name)
    else:
      # get size and make sure its not empty
      self.size = os.path.getsize(self.file_name)
    if self.size == 0:
      raise IOError("Empty image file detected!")
    self.num_blocks = self.size / self.block_bytes
    # open raw file 
    if self.read_only:
      flags = "rb"
    else:
      flags = "r+b"
    self.fh = file(self.file_name, flags)
  
  def read_blk(self, blk_num):
    if blk_num >= self.num_blocks:
      raise IOError("Invalid image file block num: got %d but max is %d" % (blk_num, self.num_blocks))
    off = blk_num * self.block_bytes
    self.fh.seek(off, os.SEEK_SET)
    return self.fh.read(self.block_bytes)
    
  def write_blk(self, blk_num, data):
    if self.read_only:
      raise IOError("Can't write block: image file is read-only")
    if blk_num >= self.num_blocks:
      raise IOError("Invalid image file block num: got %d but max is %d" % (blk_num, self.num_blocks))
    if len(data) != self.block_bytes:
      raise IOError("Invalid block size written: got %d but size is %d" % (len(data), self.block_bytes))
    off = blk_num * self.block_bytes
    self.fh.seek(off, os.SEEK_SET)
    self.fh.write(data)
  
  def close(self):
    if self.fh != None:
      self.fh.close()
      self.fh = None
  
  def create(self, num_blocks):
    if self.read_only:
      raise IOError("Can't create image file in read only mode")
    block = '\0' * self.block_bytes
    fh = file(self.file_name, "wb")
    for i in xrange(num_blocks):
      fh.write(block)
    fh.close()
  