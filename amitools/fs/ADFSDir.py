import struct
from block.Block import Block
from block.UserDirBlock import UserDirBlock
from ADFSFile import ADFSFile
from ADFSNode import ADFSNode
from FileName import FileName
from FSError import *

class ADFSDir(ADFSNode):
  def __init__(self, volume, parent, is_vol=False):
    ADFSNode.__init__(self, volume, parent)
    self.is_vol = False
    # state
    self.entries = []
    self.name_hash = []
    self.valid = False
    
  def __repr__(self):
    if self.block != None:
      return "[Dir(%d)'%s':%s]" % (self.block.blk_num, self.block.name, self.entries)
    else:
      return "[Dir]"
  
  def set_root(self, root_blk):
    self.is_vol = True
    self.set_block(root_blk)
    
  def blocks_create_old(self, anon_blk):
    ud = UserDirBlock(self.blkdev, anon_blk.blk_num)
    ud.set(anon_blk.data)
    if not ud.valid:
      raise FSError(INVALID_USER_DIR_BLOCK, block=anon_blk)
    self.set_block(ud)
    return ud
  
  def _read_add_node(self, blk, recursive):
    hash_chain = None
    node = None
    if blk.valid_chksum and blk.type == Block.T_SHORT:
      # its a userdir
      if blk.sub_type == Block.ST_USERDIR:
        node = ADFSDir(self.volume, self)
        blk = node.blocks_create_old(blk)
        if recursive:
          node.read()
      # its a file
      elif blk.sub_type == Block.ST_FILE:
        node = ADFSFile(self.volume, self)
        blk = node.blocks_create_old(blk)
      # unsupported
      else:
        raise FSError(UNSUPPORTED_DIR_BLOCK, block=blk)
    hash_chain = blk.hash_chain
    return hash_chain,node
  
  def read(self, recursive=True):
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
      hash_chain,node = self._read_add_node(blk, recursive)
      # store node in entries
      self.entries.append(node)
      # store node in name_hash
      self.name_hash[hash_idx].append(node)
      # follow hash chain
      if hash_chain != 0:
        blocks.append((hash_chain,hash_idx))
  
  def has_name(self, fn):
    fn_hash = fn.hash()
    fn_up = fn.to_upper()
    node_list = self.name_hash[fn_hash]
    for node in node_list:
      if node.name.to_upper() == fn_up:
        return True
    return False
  
  def blocks_create_new(self, free_blks, name, protect, comment, mod_time, hash_chain_blk, parent_blk):
    blk_num = free_blks[0]
    blkdev = self.blkdev
    # create a UserDirBlock
    ud = UserDirBlock(blkdev, blk_num)
    ud.create(parent_blk, name, protect, comment, mod_time, hash_chain_blk)
    ud.write()    
    self.set_block(ud)
    return blk_num
  
  def blocks_get_create_num(self):
    # the number of blocks needed for a new (empty) directory
    # -> only one UserDirBlock
    return 1
    
  def _create_node(self, node, name, protect, comment, mod_time):
    # check file name
    fn = FileName(name)
    if not fn.is_valid():
      raise FSError(INVALID_FILE_NAME, file_name=name, node=self)
    # does already exist an entry in this dir with this name?
    if self.has_name(fn):
      raise FSError(NAME_ALREADY_EXISTS, file_name=name, node=self)
    # calc hash index of name
    fn_hash = fn.hash()
    hash_chain = self.name_hash[fn_hash]
    if len(hash_chain) == 0:
      hash_chain_blk = 0
    else:
      hash_chain_blk = hash_chain[0].block.blk_num
      
    # return the number of blocks required to create this node
    num_blks = node.blocks_get_create_num()
    
    # try to find free blocks
    free_blks = self.volume.bitmap.find_n_free(num_blks)
    if free_blks == None:
      raise FSError(NO_FREE_BLOCKS, node=self, file_name=name, extra="want %d" % num_blks)
      
    # update bitmap
    for b in free_blks:
      self.volume.bitmap.clr_bit(b)
    self.volume.bitmap.write_only_bits()
      
    # now create the blocks for this node
    new_blk = node.blocks_create_new(free_blks, name, protect, comment, mod_time, hash_chain_blk, self.block.blk_num)

    # update my dir
    self.block.hash_table[fn_hash] = new_blk 
    self.block.write()
    
    # add node
    self.name_hash[fn_hash].insert(0,node)
    self.entries.append(node)
        
  def create_dir(self, name, protect=0, comment=None, mod_time=None):
    node = ADFSDir(self.volume, self)
    self._create_node(node, name, protect, comment, mod_time)
  
  def create_file(self, name, data, protect=0, comment=None, mod_time=None):
    node = ADFSFile(self.volume, self) 
    node.set_file_data(data)
    self._create_node(node, name, protect, comment, mod_time) 
  
  def _delete(self, node, wipe=False):
    # can we delete?
    if not node.can_delete():
      raise FSError(DELETE_NOT_ALLOWED, node=node)
    # make sure its a node of mine
    if node.parent != self:
      raise FSError(INTERNAL_ERROR, node=node)
    # get hash key
    hash_key = node.name.hash()
    names = self.name_hash[hash_key]
    # find my node
    pos = None
    for i in xrange(len(names)):
      if names[i] == node:
        pos = i
        break
    # hmm not found?!
    if pos == None:
      raise FSError(INTERNAL_ERROR, node=node)
    # find prev and next in hash list
    if pos > 0:
      prev = names[pos-1]
    else:
      prev = None
    if pos == len(names)-1:
      next_blk = 0
    else:
      next_blk = names[pos+1].block.blk_num
    # remove node from the hash chain
    if prev == None:
      self.block.hash_table[hash_key] = next_blk
      self.block.write()
    else:
      prev.block.hash_chain = next_blk
      prev.block.write()
    # remove from my lists
    self.entries.remove(node)
    names.remove(node)
    # remove blocks of node in bitmap
    blk_nums = node.get_block_nums()
    bm = self.volume.bitmap
    for blk_num in blk_nums:
      bm.set_bit(blk_num)
    bm.write_only_bits()
    # (optional) wipe blocks
    if wipe:
      clr_blk = '\0' * self.blkdev.block_bytes
      for blk_num in blk_nums:
        self.blkdev.write_block(blk_num, clr_blk)
    
  def can_delete(self):
    return len(self.entries) == 0
  
  def get_entries_sorted_by_name(self):
    return sorted(self.entries, key=lambda x : x.name.to_upper())
  
  def dump(self):
    print "Dir(%d)" % self.block.blk_num
    print " entries: %s" % self.entries
  
  def list(self, indent=0, all=False):
    istr = "  " * indent
    if self.is_vol:
      tstr = "VOL"
      pstr = ""
    else:
      tstr = "DIR"
      pstr = str(self.block.protect_flags)
    print "%-40s       %s  %7s  %s" % (istr + self.block.name, tstr, pstr, self.block.mod_ts)
    if not all and indent > 0:
      return
    if self.entries:
      es = self.get_entries_sorted_by_name()
      for e in es:
        e.list(indent=indent+1, all=all)
    
  def get_path(self, pc, allow_file=True, allow_dir=True):
    if len(pc) == 0:
      return self
    for e in self.entries:
      if e.name.to_upper() == pc[0].to_upper():
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
    
  def draw_on_bitmap(self, bm, show_all=False):
    blk_num = self.block.blk_num
    if self.is_vol:
      bm[blk_num] = 'V'
    else:
      bm[blk_num] = 'D'
    if show_all:
      for e in self.entries:
        e.draw_on_bitmap(bm, True)

  def get_block_nums(self):
    return [self.block.blk_num]
