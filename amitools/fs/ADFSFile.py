from FileListBlock import FileListBlock
from FileDataBlock import FileDataBlock

class ADFSFile:
  def __init__(self, hdr_blk):
    self.hdr_blk = hdr_blk
    self.ext_blks = []
    self.data_blk_nums = []
    self.valid = False
  
  def __repr__(self):
    return "[File(%d)'%s':%d]" % (self.hdr_blk.blk_num, self.hdr_blk.name, self.hdr_blk.byte_size)
  
  def scan(self):
    """scan for the data block numbers and look up list blocks"""
    self.data_blk_nums = self.hdr_blk.data_blocks[:]
    next_ext = self.hdr_blk.extension
    while next_ext != 0:
      ext_blk = FileListBlock(self.hdr_blk.blkdev, next_ext)
      ext_blk.read()
      if not ext_blk.valid:
        return False
      next_ext = ext_blk.extension
      self.ext_blks.append(ext_blk)
      self.data_blk_nums += ext_blk.data_blocks
    self.valid = True
    return self.valid
  
  def read(self):
    """read data blocks"""
    self.data_blks = []
    want_seq_num = 1
    total_size = 0
    for blk in self.data_blk_nums:
      dat_blk = FileDataBlock(self.hdr_blk.blkdev, blk)
      dat_blk.read()
      if not dat_blk.valid:
        return False
      # check sequence number
      if dat_blk.seq_num != want_seq_num:
        return False
      self.data_blks.append(dat_blk)
      want_seq_num += 1
      total_size += dat_blk.data_size
    # check if total size matches
    self.valid = (total_size == self.hdr_blk.byte_size)
    return self.valid
  
  def list(self, indent=0):
    print " " * indent,"%-30s  %8d  %s  %s" % (self.hdr_blk.name, self.hdr_blk.byte_size, self.hdr_blk.mod_ts, self.data_blk_nums)
    