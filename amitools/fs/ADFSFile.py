from FileListBlock import FileListBlock
from FileDataBlock import FileDataBlock
from ADFSNode import ADFSNode

class ADFSFile(ADFSNode):
  def __init__(self, volume, hdr_blk, hash_idx):
    ADFSNode.__init__(self, volume, hdr_blk, hash_idx)
    self.ext_blks = []
    self.data_blk_nums = []
    self.data_blks = None
    self.valid = False
  
  def __repr__(self):
    return "[File(%d)'%s':%d]" % (self.block.blk_num, self.block.name, self.block.byte_size)
  
  def scan(self):
    """scan for the data block numbers and look up list blocks"""
    self.data_blk_nums = self.block.data_blocks[:]
    next_ext = self.block.extension
    while next_ext != 0:
      ext_blk = FileListBlock(self.block.blkdev, next_ext)
      ext_blk.read()
      if not ext_blk.valid:
        return False
      next_ext = ext_blk.extension
      self.ext_blks.append(ext_blk)
      self.data_blk_nums += ext_blk.data_blocks
    self.valid = True
    # get public values
    self.name = self.block.name
    return self.valid
  
  def read(self):
    """read data blocks"""
    self.data_blks = []
    want_seq_num = 1
    total_size = 0
    is_ffs = self.volume.is_ffs
    byte_size = self.block.byte_size
    for blk in self.data_blk_nums:
      if is_ffs:
        # ffs has raw data blocks
        dat_blk = self.volume.blkdev.read_block(blk)
        if dat_blk == None:
          return False
        total_size += len(dat_blk)
        if total_size > byte_size:
          shrink = total_size - byte_size
          dat_blk = dat_blk[:-shrink-1]
          total_size = byte_size
        self.data_blks.append(dat_blk)
      else:
        # ofs
        dat_blk = FileDataBlock(self.block.blkdev, blk)
        dat_blk.read()
        if not dat_blk.valid:
          return False
        # check sequence number
        if dat_blk.seq_num != want_seq_num:
          return False
        self.data_blks.append(dat_blk)
        total_size += dat_blk.data_size
      want_seq_num += 1
    # check if total size matches
    self.valid = (total_size == byte_size)
    return self.valid
  
  def get_file_data(self):
    if self.data_blks == None:
      if not self.read():
        return None
    data = ""
    is_ffs = self.volume.is_ffs
    for blk in self.data_blks:
      if is_ffs:
        data += blk
      else:
        data += blk.get_block_data()
    return data
  
  def list(self, indent=0):
    istr = "  " * indent
    print "%-40s  %8d  %s  %s" % (istr + self.block.name, self.block.byte_size, self.block.protect_flags, self.block.mod_ts)
    