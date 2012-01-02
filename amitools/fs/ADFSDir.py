import struct
from Block import Block
from UserDirBlock import UserDirBlock
from FileHeaderBlock import FileHeaderBlock
from ADFSFile import ADFSFile
from ADFSNode import ADFSNode
from FileName import FileName

class ADFSDir(ADFSNode):
  def __init__(self, volume, block, hash_idx=0, is_vol=False):
    ADFSNode.__init__(self, volume, block, hash_idx)
    self.is_vol = is_vol
    self.blkdev = block.blkdev
    self.block_bytes = self.blkdev.block_bytes
    self.entries = None
    self.name_hash = None
    self.valid = False
    self.invalid_blocks = []
    
  def __repr__(self):
    return "[Dir(%d)'%s':%s,errs=%s]" % (self.block.blk_num, self.block.name, self.entries, self.invalid_blocks)
  
  def _create_node(self, blk, hash_idx, recursive):
    ok = False
    hash_chain = None
    node = None
    if blk.valid_chksum and blk.type == Block.T_SHORT:
      # its a userdir
      if blk.sub_type == Block.ST_USERDIR:
        user_dir_blk = UserDirBlock(self.blkdev, blk.blk_num)
        user_dir_blk.set(blk.data)
        if user_dir_blk.valid:
          user_dir = ADFSDir(self.volume, user_dir_blk, hash_idx)
          if recursive:
            ok = user_dir.read()
          else:
            ok = True
          node = user_dir
          hash_chain = user_dir_blk.hash_chain
      # its a file
      elif blk.sub_type == Block.ST_FILE:
        file_hdr_blk = FileHeaderBlock(self.blkdev, blk.blk_num)
        file_hdr_blk.set(blk.data)
        if file_hdr_blk.valid:
          afile = ADFSFile(self.volume, file_hdr_blk, hash_idx)
          ok = afile.scan()
          node = afile
          hash_chain = file_hdr_blk.hash_chain
    return ok,hash_chain,node
  
  def read(self, recursive=True):
    self.entries = []
    self.name_hash = []
    self.valid = False
    self.invalid_blocks = []
    self.name = self.block.name

    # create initial list with blk_num/hash_index for dir scan
    blocks = []
    for i in xrange(self.block.hash_size):
      blk_num = self.block.hash_table[i]
      if blk_num != 0:
        blocks.append((blk_num,i))
      self.name_hash.append([])
  
    for blk_num,hash_idx in blocks:
      # read anonymous block
      blk = Block(self.blkdev, blk_num)
      blk.read()
      # create file/dir node
      ok,hash_chain,node = self._create_node(blk, hash_idx, recursive)
      if ok:
        # store node in entries
        self.entries.append(node)
        # store node in name_hash
        self.name_hash[hash_idx].append(node)
        # follow hash chain
        if hash_chain != 0:
          blocks.append((hash_chain,hash_idx))
      else:
        # can't parse node
        self.invalid_blocks.append(blk_num)
        
    self.valid = len(self.invalid_blocks) == 0
    return self.valid
  
  def has_name(self, fn):
    fn_hash = fn.hash()
    fn_up = fn.to_upper()
    node_list = self.name_hash[fn_hash]
    for node in node_list:
      fn = FileName(node.name)
      if fn.to_upper() == fn_up:
        return True
    return False
    
  def create_dir(self, name, protect=0, comment=None, mod_time=None):
    # check file name
    fn = FileName(name)
    if not fn.is_valid():
      return False
    # does already exist with this name?
    if self.has_name(fn):
      return False  
    # hash index
    fn_hash = fn.hash()
    hash_chain = self.name_hash[fn_hash]
    if len(hash_chain) == 0:
      hash_chain_blk = 0
    else:
      hash_chain_blk = hash_chain[0].block.blk_num   

    # find a free block for UserDirBlock
    bitmap = self.volume.bitmap
    new_blk = bitmap.find_free()
    if new_blk == None:
      return False
    # create a new user dir block
    ud = UserDirBlock(self.blkdev, new_blk)
    ud.create(self.block.blk_num, name, protect, comment, mod_time, hash_chain_blk)
    ud.write()

    # update my dir
    self.block.hash_table[fn_hash] = new_blk 
    self.block.write()

    # finally allocate block and update bitmap
    bitmap.clr_bit(new_blk)
    bitmap.write()
    
    # create dir node
    node = ADFSDir(self.volume, ud, fn_hash)
    node.read()
    self.name_hash[fn_hash].insert(0,node)
    self.entries.append(node)
    return True
  
  def get_entries_sorted_by_name(self):
    return sorted(self.entries, key=lambda x : x.name)
  
  def dump(self):
    print "Dir(%d)" % self.block.blk_num
    print " entries: %s" % self.entries
    print " invalid blocks: %s" % self.invalid_blocks
  
  def list(self, indent=0):
    istr = "  " * indent
    if self.is_vol:
      tstr = "VOL"
      pstr = ""
    else:
      tstr = "DIR"
      pstr = str(self.block.protect_flags)
    print "%-40s       %s  %7s  %s" % (istr + self.block.name, tstr, pstr, self.block.mod_ts)
    if self.entries:
      es = self.get_entries_sorted_by_name()
      for e in es:
        e.list(indent=indent+1)
    
  def get_path(self, pc, allow_file=True, allow_dir=True):
    if len(pc) == 0:
      return self
    for e in self.entries:
      fn = FileName(e.name)
      if fn.to_upper() == pc[0].to_upper():
        if len(pc) > 1:
          if isinstance(e, ADFSDir):
            return e.get_path(pc[1:], allow_file, allow_dir)
          else:
            return None
        else:
          if isinstance(e, ADFSDir):
            if allow_dir:
              return e
            else:
              return None
          elif isinstance(e, ADFSFile):
            if allow_file:
              return e
            else:
              return None
          else:
            return None
    return None
