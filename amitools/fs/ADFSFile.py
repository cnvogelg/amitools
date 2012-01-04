from block.FileHeaderBlock import FileHeaderBlock
from block.FileListBlock import FileListBlock
from block.FileDataBlock import FileDataBlock
from ADFSNode import ADFSNode
from FSError import *

class ADFSFile(ADFSNode):
  def __init__(self, volume):
    ADFSNode.__init__(self, volume)
    # state
    self.ext_blks = []
    self.data_blk_nums = []
    self.data_blks = []
    self.valid = False
    self.data = None
    self.data_size = 0
    self.total_blks = 0
  
  def __repr__(self):
    return "[File(%d)'%s':%d]" % (self.block.blk_num, self.block.name, self.block.byte_size)
  
  def blocks_create_old(self, anon_blk):
    # create file header block
    fhb = FileHeaderBlock(self.blkdev, anon_blk.blk_num)
    fhb.set(anon_blk.data)
    if not fhb.valid:
      raise FSError(INVALID_FILE_HEADER_BLOCK, block=anon_blk)
    self.set_block(fhb)

    # retrieve data blocks and size from header
    self.data_blk_nums = fhb.data_blocks[:]
    self.data_size = fhb.byte_size

    # scan for extension blocks
    next_ext = self.block.extension
    while next_ext != 0:
      ext_blk = FileListBlock(self.block.blkdev, next_ext)
      ext_blk.read()
      if not ext_blk.valid:
        raise FSError(INVALID_FILE_LIST_BLOCK, block=ext_blk)
      next_ext = ext_blk.extension
      self.ext_blks.append(ext_blk)
      self.data_blk_nums += ext_blk.data_blocks
    
    # now check number of ext blocks
    self.num_ext_blks = self.calc_number_of_list_blks()
    my_num_ext_blks = len(self.ext_blks)
    if my_num_ext_blks != self.num_ext_blks:
      raise FSError(FILE_LIST_BLOCK_COUNT_MISMATCH, node=self, extra="got=%d want=%d" % (my_num_ext_blks, self.num_ext_blks))

    # now check number of data blocks
    self.num_data_blks = self.calc_number_of_data_blks()
    my_num_data_blks = len(self.data_blk_nums)
    if my_num_data_blks != self.num_data_blks:
      raise FSError(FILE_DATA_BLOCK_COUNT_MISMATCH, node=self, extra="got=%d want=%d" % (my_num_data_blks, self.num_data_blks))

    # calc number of total blocks occupied by this file
    self.total_blks = 1 + my_num_ext_blks + my_num_data_blks

    return fhb
  
  def read(self):
    """read data blocks"""
    self.data_blks = []
    want_seq_num = 1
    total_size = 0
    is_ffs = self.volume.is_ffs
    byte_size = self.block.byte_size
    data = ""
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
        data += dat_blk
      else:
        # ofs
        dat_blk = FileDataBlock(self.block.blkdev, blk)
        dat_blk.read()
        if not dat_blk.valid:
          raise FSError(INVALID_FILE_DATA_BLOCK, block=dat_blk)
        # check sequence number
        if dat_blk.seq_num != want_seq_num:
          raise FSError(INVALID_SEQ_NUM, block=dat_blk, extra="got=%d wanted=%d" % (dat_blk.seq_num, want_seq_num))
        # store data blocks
        self.data_blks.append(dat_blk)
        total_size += dat_blk.data_size
        data += dat_blk.get_block_data()
      want_seq_num += 1
    # store full contents of file
    self.data = data
  
  def get_file_data(self):
    if self.data != None:
      return self.data
    self.read()
    return self.data
  
  def set_file_data(self, data):
    self.data = data
    self.data_size = len(data)
    self.num_data_blks = self.calc_number_of_data_blks()
    self.num_ext_blks = self.calc_number_of_list_blks()
  
  def get_data_block_contents_bytes(self):
    """how many bytes of file data can be stored in a block?"""
    bb = self.volume.blkdev.block_bytes
    if self.volume.is_ffs:
      return bb
    else:
      return bb - 24
  
  def calc_number_of_data_blks(self):
    """given the file size: how many data blocks do we need to store the file?"""
    bb = self.get_data_block_contents_bytes()
    ds = self.data_size
    return int((ds + bb -1) / bb)
  
  def calc_number_of_list_blks(self):
    """given the file size: how many list blocks do we need to store the data blk ptrs?"""
    db = self.calc_number_of_data_blks()
    # ptr per block
    ppb = self.volume.blkdev.block_longs - 56
    # fits in header block?
    if db <= ppb:
      return 0
    else:
      db -= ppb
      return (db + ppb - 1) / ppb 
  
  def blocks_get_create_num(self):
    # determine number of blocks to create
    return 1 + self.num_data_blks + self.num_ext_blks
  
  def blocks_create_new(self, free_blks, name, protect, comment, mod_time, hash_chain_blk, parent_blk):
    # assign block numbers
    fhb_num = free_blks[0]
    # ... for ext
    ext_nums = []
    for i in xrange(self.num_ext_blks):
      ext_nums.append(free_blks[1+i])
    # ... for data
    off = 1 + self.num_ext_blks
    self.data_blk_nums = []
    for i in xrange(self.num_data_blks):
      self.data_blk_nums.append(free_blks[off])
      off += 1
    
    ppb = self.volume.blkdev.block_longs - 56 # data pointer per block
    
    # create file header block
    fhb = FileHeaderBlock(self.blkdev, fhb_num)
    byte_size = len(self.data)
    if self.num_data_blks > ppb:
      hdr_blks = self.data_blk_nums[0:ppb]
      hdr_ext = ext_nums[0]
    else:
      hdr_blks = self.data_blk_nums
      hdr_ext = 0
    fhb.create(parent_blk, name, hdr_blks, hdr_ext, byte_size, protect, comment, mod_time, hash_chain_blk)
    fhb.write() 
    self.set_block(fhb)
    
    # create file list (=ext) blocks
    ext_off = ppb
    for i in xrange(self.num_ext_blks):
      flb = FileListBlock(self.blkdev, ext_nums[i])
      if i == self.num_ext_blks - 1:
        ext_blk = 0
      else:
        ext_blk = ext_nums[i+1]
      blks = data_nums[ext_off:ext_off+pbb]
      flb.create(parent_blk, blks, ext_blk)
      flb.write()
      self.ext_blks.append(flb)
      ext_off += ppb
    
    # write data blocks
    self.write()

    self.valid = True    
    return fhb_num
  
  def write(self):
    off = 0
    left = self.data_size
    blk_idx = 0
    bs = self.get_data_block_contents_bytes()
    is_ffs = self.volume.is_ffs
    while off < self.data_size:
      # number of data block
      blk_num = self.data_blk_nums[blk_idx]
      # extract file data
      size = left
      if size > bs:
        size = bs
      d = self.data[off:off+size]
      if is_ffs:
        # pad block
        if size < bs:
          d += '\0' * (bs-size)
        # write raw block data in FFS
        self.blkdev.write_block(blk_num, d)
      else:
        # old FS: create and write data block
        fdb = FileDataBlock(self.blkdev, blk_num)
        if blk_idx == self.num_data_blks - 1:
          next_data = 0
        else:
          next_data = self.data_blk_nums[blk_idx+1]
        fdb.create(self.block.blk_num, blk_idx+1, d, next_data)
        fdb.write()
        self.data_blks.append(fdb)
      blk_idx += 1
      off += bs
  
  def list(self, indent=0):
    istr = "  " * indent
    print "%-40s  %8d  %s  %s" % (istr + self.block.name, self.block.byte_size, self.block.protect_flags, self.block.mod_ts)
    