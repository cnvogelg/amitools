from amitools.fs.block.Block import Block
from amitools.fs.block.BootBlock import BootBlock
from amitools.fs.block.UserDirBlock import UserDirBlock
from amitools.fs.block.RootBlock import RootBlock
from amitools.fs.block.FileHeaderBlock import FileHeaderBlock
from amitools.fs.block.FileListBlock import FileListBlock
from amitools.fs.block.FileDataBlock import FileDataBlock
from amitools.fs.FSString import FSString
from amitools.fs.FileName import FileName

class ValidatorRemark:
  """A class to report the validator status"""
  DEBUG = 0
  INFO = 1
  WARN = 2
  ERROR = 3
  FATAL = 4
  names = ('debug','info ','WARN ','ERROR','FATAL')
  
  def __init__(self, level, msg, blk_num=-1):
    self.blk_num = blk_num
    self.level = level
    self.msg = msg
  def __str__(self):
    if self.blk_num == -1:
      return "%s%s:%s" % (" "*8, self.names[self.level], self.msg)
    else:
      return "@%06d:%s:%s" % (self.blk_num, self.names[self.level], self.msg)

class Validator:
  """Validate an AmigaDOS file system"""

  # block map types
  BM_UNKNOWN = 0
  BM_READ_ERROR = 1
  BM_INVALID = 2
  BM_ROOT_OK = 3
  BM_ROOT_BROKEN = 4
  BM_DIR_OK = 5
  BM_DIR_BROKEN = 6
  BM_FH_OK = 7
  BM_FH_BROKEN = 8
  BM_FL_OK = 9
  BM_FL_BROKEN = 10
  BM_FD_OK = 11
  BM_FD_BROKEN = 12
  BM_VALID = 13
  
  def __init__(self, blkdev, debug=True):
    self.blkdev = blkdev
    self.remarks = []
    self.debug = debug
    self.boot = None
  
  def log(self, level, msg, blk_num = -1):
    if not self.debug and level == ValidatorRemark.DEBUG:
      return
    rem = ValidatorRemark(level, msg, blk_num)
    self.remarks.append(rem)
  
  def dump_log(self):
    for r in self.remarks:
      print r

  def scan_boot(self):
    """First scan stage is: scan_boot.
       Returns True if boot block has a valid dos type.
       Invalid checksum of the block is tolerated but remarked.
    """
    # check boot block
    boot = BootBlock(self.blkdev)
    boot.read()
    if boot.valid:
      # dos type is valid
      self.boot = boot
      # give a warning if checksum is not correct
      if boot.valid_chksum:
        self.log(ValidatorRemark.WARN,"invalid boot block checksum",0)
      return True
    else:
      self.log(ValidatorRemark.WARN,"invalid boot block dos type",0)
      return False
  
  def scan_root(self):
    """Second scan stage is: scan_root.
       Try to determine root block from boot block or guess number.
       Returns True if the root block could be decoded.
    """
    if self.boot != None:
      # retrieve root block number from boot block
      root_blk_num = self.boot.got_root_blk
      # check root block number
      if root_blk_num < self.blkdev.reserved or root_blk_num > self.blkdev.num_blocks:
        root_blk_num = self.blkdev.num_blocks / 2
        self.log(ValidatorRemark.ERROR,"Invalid root block number: using guess",root_blk_num)
    else:
      # guess root block number
      root_blk_num = self.blkdev.num_blocks / 2
      self.log(ValidatorRemark.INFO,"Guessed root block number",root_blk_num)
    # read root block
    root = RootBlock(self.blkdev, root_blk_num)
    root.read()
    if not root.valid:
      self.log(ValidatorRemark.ERROR,"Root block is not valid",root_blk_num)      
      self.root = None # mode without root
      return False
    else:
      self.root = root
      return True
  
  def scan_blocks(self, debug=True):
    """Third scan stage: blocks.
       Return True if there is a chance that a file system will be found there
    """
    begin_blk = self.blkdev.reserved
    num_blk = self.blkdev.num_blocks - self.blkdev.reserved
    block_state = [self.BM_UNKNOWN] * num_blk
    blocks = [None] * num_blk
    # setup block classifcation
    dir_blocks = {}
    root_blocks = {}
    valid_blocks = {}
    invalid_blocks = {}
    file_hdr_blocks = {}
    file_list_blocks = {}
    file_data_blocks = {}
    error_blocks = {}
    self.log(ValidatorRemark.DEBUG,"block: checking range: +%d num=%d" % (begin_blk, num_blk))
    # scan all blocks
    for n in range(num_blk):
      blk_num = n + begin_blk
      try:
        blk = Block(self.blkdev, blk_num)
        blk.read()
        blocks[n] = blk
        state = self.BM_UNKNOWN
        if blk.valid:
          # block is valid AmigaDOS
          # --- root block ---
          if blk.is_root_block():
            root = RootBlock(self.blkdev, blk_num)
            root.read()
            if root.valid:
              root_blocks[blk_num] = root
              name = FSString(root.name)
              self.log(ValidatorRemark.INFO, "Found Root: '%s'" % name, blk_num)
              state = self.BM_ROOT_OK
            else:
              error_blocks[blk_num] = blk
              state = self.BM_ROOT_BROKEN
          # --- user dir block ---
          elif blk.is_user_dir_block():
            user = UserDirBlock(self.blkdev, blk_num)
            user.read()
            if user.valid:
              dir_blocks[blk_num] = user
              name = FSString(user.name)
              self.log(ValidatorRemark.INFO, "Found Dir : '%s'" % name, blk_num)
              state = self.BM_DIR_OK
            else:
              error_blocks[blk_num] = blk
              state = self.BM_DIR_BROKEN
          # --- filter header block ---
          elif blk.is_file_header_block():
            fh = FileHeaderBlock(self.blkdev, blk_num)
            fh.read()
            if fh.valid:
              file_hdr_blocks[blk_num] = fh
              name = FSString(fh.name)
              self.log(ValidatorRemark.INFO, "Found File: '%s'" % name, blk_num)
              state = self.BM_FH_OK
            else:
              error_blocks[blk_num] = blk
              state = self.BM_FH_BROKEN
          # --- file list block ---
          elif blk.is_file_list_block():
            fl = FileListBlock(self.blkdev, blk_num)
            fl.read()
            if fl.valid:
              file_list_blocks[blk_num] = fl
              state = self.BM_FL_OK
            else:
              error_blocks[blk_num] = blk
              state = self.BM_FL_BROKEN
          # --- file data block (OFS) ---
          elif blk.is_file_data_block():
            fd = FileDataBlock(self.blkdev, blk_num)
            fd.read()
            if fd.valid:
              file_data_blocks[blk_num] = fd
              state = self.BM_FD_OK
            else:
              error_blocks[blk_num] = blk
              state = self.BM_FD_BROKEN
          # --- unknown ---
          else:
            valid_blocks[blk_num] = blk
            state = self.BM_VALID
          # finally store state
          block_state[n] = state
        else:
          block_state[n] = self.BM_INVALID
          invalid_blocks[blk_num] = blk
      except IOError,e:
        self.log(ValidatorRemark.ERROR, "Can't read block", blk_num)
        block_state[n] = self.BM_READ_ERROR
    # first summary after block scan
    num_error_blocks = len(error_blocks)
    if num_error_blocks > 0:
      self.log(ValidatorRemark.ERROR, "%d error blocks found" % num_error_blocks)
    num_valid_blocks = len(valid_blocks)
    if num_valid_blocks > 0:
      self.log(ValidatorRemark.INFO, "%d valid but unknown blocks found" % num_valid_blocks)
    num_invalid_blocks = len(invalid_blocks)
    if num_invalid_blocks > 0:
      self.log(ValidatorRemark.INFO, "%d invalid blocks found" % num_invalid_blocks)
    # store block map
    self.block_state = block_state
    self.blocks = blocks 
    self.dir_blocks = dir_blocks
    self.file_hdr_blocks = file_hdr_blocks
    self.file_list_blocks = file_list_blocks
    self.file_data_blocks = file_data_blocks
    self.invalid_blocks = invalid_blocks
    self.valid_blocks = valid_blocks
    self.error_blocks = error_blocks
    self.root_blocks = root_blocks
    # give first statistics
    self.num_dirs = len(self.dir_blocks)
    self.num_files = len(self.file_hdr_blocks)
    if self.root != None:
      self.num_dirs += 1
    self.any_chance = (self.num_files > 0) or (self.num_dirs > 0)
    return self.any_chance

  def scan_dirs(self):
    """Stage 4: scan through all found directories"""
    valid_dirs = []
    broken_dirs = []
    # scan root dir(s)
    for b in self.root_blocks:
      root = self.root_blocks[b]
      ok,dir_obj = self.scan_dir(root)
      if ok:
        valid_dirs.append(dir_obj)
      else:
        broken_dirs.append(dir_obj)
    # scan user dirs
    for b in self.dir_blocks:
      user = self.dir_blocks[b]
      ok,dir_obj = self.scan_dir(user)
      if ok:
        valid_dirs.append(dir_obj)
      else:
        broken_dirs.append(dir_obj)
    # store result
    self.valid_dirs = valid_dirs
    self.broken_dirs = broken_dirs
  
  def scan_dir(self, dir_blk):    
    """check a directory by scanning through the hash table entries and follow the chains
       Returns (all_chains_ok, dir_obj)
    """
    # run through hash_table of directory
    hash_val = 0
    chains = {}
    all_chains_ok = True
    for blk in dir_blk.hash_table:
      if blk != 0:
        # build chain
        chain = []
        chain_terminated_ok = self.check_dir_chain(hash_val, blk, dir_blk, chain)
        # validate chain
        all_parent_ok = True
        all_hash_ok = True
        for c in chain:
          if not c[1]:
            all_parent_ok = False
          if not c[2]:
            all_hash_ok = False
        chain_ok = chain_terminated_ok and all_parent_ok and all_hash_ok
        # store chain result in map for hash
        chains[hash_val] = (chain, chain_terminated_ok, all_parent_ok, all_hash_ok, chain_ok)
        all_chains_ok = all_chains_ok and chain_ok
      hash_val += 1
    # create a dir object
    dir_obj = { 'chains':chains, 'dir_blk':dir_blk }
    return (all_chains_ok, dir_obj)
    
  def check_dir_chain(self, hash_val, blk_num, dir_blk, chain):
    """check the blocks along a chain.
       Return True if the chain is terminated correctly.
       Store (blk, parent_ok, name_hash_ok) tuples in chain list to show valid parents.
    """
    dir_blk_num = dir_blk.blk_num
    if blk_num in self.dir_blocks:
      # is a directory block in chain
      blk = self.dir_blocks[blk_num]
    elif blk_num in self.file_hdr_blocks:
      # is a file block in chain
      blk = self.file_hdr_blocks[blk_num]
    else:
      # unknown entry
      dir_name = FSString(dir_blk.name)
      self.log(ValidatorRemark.ERROR, "invalid block terminates chain #%d of dir '%s' (%d)" % (hash_val, dir_name, dir_blk_num), blk_num)
      return False
    
    # check parent of block
    name = FSString(blk.name)
    parent_blk = blk.parent
    parent_ok = (parent_blk == dir_blk_num)
    if not parent_ok:
      self.log(ValidatorRemark.ERROR, "invalid parent in '%s' chain #%d of dir '%s' (%d)" % (name, hash_val, dir_name, dir_blk_num), blk_num)

    # check name hash
    fn = FileName(name)
    fn_hash = fn.hash()
    fn_hash_ok = (fn_hash == hash_val)
    if not fn_hash_ok:
      self.log(ValidatorRemark.ERROR, "invalid name hash in '%s' chain #%d of dir '%s' (%d)" % (name, hash_val, dir_name, dir_blk_num), blk_num)      

    # store in chain: blk and parent_ok
    chain.append((blk, parent_ok, fn_hash_ok))
      
    # check next block in chain
    next_blk = blk.hash_chain
    if next_blk != 0:
      return self.check_dir_chain(hash_val, next_blk, dir_blk, chain)
    else:  
      return True
