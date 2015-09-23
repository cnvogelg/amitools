import os
import stat
import amitools.util.BlkDevTools as BlkDevTools
import zlib
import io

class ImageFile:
  def __init__(self, file_name, read_only=False, block_bytes=512, fobj=None):
    self.file_name = file_name
    self.read_only = read_only
    self.block_bytes = block_bytes
    self.fobj = fobj
    self.fh = None
    self.size = 0
    self.num_blocks = 0

  def open(self):
    # file obj?
    if self.fobj is not None:
      self.fh = self.fobj
      # get size via seek
      self.fobj.seek(0,2) # end of file
      self.size = self.fobj.tell()
      self.fobj.seek(0,0) # return to begin
      self.num_blocks = self.size / self.block_bytes
    # file name given
    else:
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
      self.fh = io.open(self.file_name, flags)

  def read_blk(self, blk_num):
    if blk_num >= self.num_blocks:
      raise IOError("Invalid image file block num: got %d but max is %d" % (blk_num, self.num_blocks))
    off = blk_num * self.block_bytes
    if off != self.fh.tell():
      self.fh.seek(off, os.SEEK_SET)
    num = self.block_bytes
    data = self.fh.read(self.block_bytes)
    return data

  def write_blk(self, blk_num, data):
    if self.read_only:
      raise IOError("Can't write block: image file is read-only")
    if blk_num >= self.num_blocks:
      raise IOError("Invalid image file block num: got %d but max is %d" % (blk_num, self.num_blocks))
    if len(data) != self.block_bytes:
      raise IOError("Invalid block size written: got %d but size is %d" % (len(data), self.block_bytes))
    off = blk_num * self.block_bytes
    if off != self.fh.tell():
      self.fh.seek(off, os.SEEK_SET)
    self.fh.write(data)

  def flush(self):
    self.fh.flush()

  def close(self):
    if self.fh != None:
      self.fh.close()
      self.fh = None

  def create(self, num_blocks):
    if self.read_only:
      raise IOError("Can't create image file in read only mode")
    block = '\0' * self.block_bytes
    if self.fobj is not None:
      for i in xrange(num_blocks):
        self.fobj.write(block)
      self.fobj.seek(0,0)
    else:
      fh = file(self.file_name, "wb")
      for i in xrange(num_blocks):
        fh.write(block)
      fh.close()


# --- mini test ---
if __name__ == '__main__':
  import sys
  for a in sys.argv[1:]:
    # read image
    im = ImageFile(a)
    im.open()
    d = im.read_blk(0)
    im.write_blk(0,d)
    im.close()
    # read fobj
    fobj = file(a,"r+b")
    im = ImageFile(a,fobj=fobj)
    im.open()
    d = im.read_blk(0)
    im.write_blk(0,d)
    im.close()
