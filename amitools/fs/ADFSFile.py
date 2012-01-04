from FileHeaderBlock import FileHeaderBlock
from FileListBlock import FileListBlock
from FileDataBlock import FileDataBlock
from ADFSNode import ADFSNode
from FSError import *

class ADFSFile(ADFSNode):
  def __init__(self, volume):
    ADFSNode.__init__(self, volume)
    # state
    self.ext_blks = []
    self.data_blk_nums = []
    self.data_blks = None
    self.valid = False
    self.data = None
  
  def __repr__(self):
    return "[File(%d)'%s':%d]" % (self.block.blk_num, self.block.name, self.block.byte_size)
  
  def blocks_create_old(self, anon_blk):
    # create file header block
    fhb = FileHeaderBlock(self.blkdev, anon_blk.blk_num)
    fhb.set(anon_blk.data)
    if not fhb.valid:
      raise FSError(INVALID_FILE_HEADER_BLOCK, block=anon_blk)
    self.set_block(fhb)
    # scan for extension blocks
    self.data_blk_nums = fhb.data_blocks[:]
    next_ext = self.block.extension
    while next_ext != 0:
      ext_blk = FileListBlock(self.block.blkdev, next_ext)
      ext_blk.read()
      if not ext_blk.valid:
        raise FSError(INVALID_FILE_LIST_BLOCK, block=ext_blk)
      next_ext = ext_blk.extension
      self.ext_blks.append(ext_blk)
      self.data_blk_nums += ext_blk.data_blocks
    return fhb
  
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
        total_size += len(dat_blk)
        # shrink last read id necessary
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
          raise FSError(INVALID_FILE_DATA_BLOCK, block=dat_blk)
        # check sequence number
        if dat_blk.seq_num != want_seq_num:
          raise FSError(INVALID_SEQ_NUM, block=dat_blk, extra="got=%d wanted=%d" % (dat_blk.seq_num, want_seq_num))
        self.data_blks.append(dat_blk)
        total_size += dat_blk.data_size
      want_seq_num += 1
  
  def get_file_data(self):
    if self.data != None:
      return self.data
    if self.data_blks == None:
      self.read()
    data = ""
    is_ffs = self.volume.is_ffs
    for blk in self.data_blks:
      if is_ffs:
        data += blk
      else:
        data += blk.get_block_data()
    self.data = data
    return data
  
  def set_file_data(self, data):
    self.data = data
  
  def blocks_get_create_num(self):
    # determine number of blocks to create
    return 1
  
  def blocks_create_new(self, free_blks, name, protect, comment, mod_time, hash_chain_blk, parent_blk):
    fhb_num = free_blks[0]
    # create new file blocks
    fhb = FileHeaderBlock(self.blkdev, fhb_num)
    byte_size = len(self.data)
    data_blks = []
    extension = 0
    fhb.create(parent_blk, name, byte_size, data_blks, protect, comment, mod_time, hash_chain_blk, extension)
    fhb.write()    
    self.set_block(fhb)
    
    
    return fhb_num
  
  def list(self, indent=0):
    istr = "  " * indent
    print "%-40s  %8d  %s  %s" % (istr + self.block.name, self.block.byte_size, self.block.protect_flags, self.block.mod_ts)
    