import struct
from block.Block import Block
from block.UserDirBlock import UserDirBlock
from block.DirCacheBlock import DirCacheBlock 
from ADFSFile import ADFSFile
from ADFSNode import ADFSNode
from FileName import FileName
from FSError import *
from MetaInfo import *

class ADFSDir(ADFSNode):
  def __init__(self, volume, parent):
    ADFSNode.__init__(self, volume, parent)
    # state
    self.entries = None
    self.dcache_blks = None
    self.name_hash = None
    self.valid = False
    
  def __repr__(self):
    if self.block != None:
      return "[Dir(%d)'%s':%s]" % (self.block.blk_num, self.block.name, self.entries)
    else:
      return "[Dir]"
  
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
  
  def _init_name_hash(self):
    self.name_hash = []
    for i in xrange(self.block.hash_size):
      self.name_hash.append([])      
  
  def read(self, recursive=False):
    self._init_name_hash()
    self.entries = [] 
     
    # create initial list with blk_num/hash_index for dir scan
    blocks = []
    for i in xrange(self.block.hash_size):
      blk_num = self.block.hash_table[i]
      if blk_num != 0:
        blocks.append((blk_num,i))
  
    for blk_num,hash_idx in blocks:
      # read anonymous block
      blk = Block(self.blkdev, blk_num)
      blk.read()
      if not blk.valid:
        self.valid = False
        return
      # create file/dir node
      hash_chain,node = self._read_add_node(blk, recursive)
      # store node in entries
      self.entries.append(node)
      # store node in name_hash
      self.name_hash[hash_idx].append(node)
      # follow hash chain
      if hash_chain != 0:
        blocks.append((hash_chain,hash_idx))
    
    # dircaches available?
    if self.volume.is_dircache:
      self.dcache_blks = []
      dcb_num = self.block.extension
      while dcb_num != 0:
        dcb = DirCacheBlock(self.blkdev, dcb_num)
        dcb.read()
        if not dcb.valid:
          self.valid = False
          return
        self.dcache_blks.append(dcb)
        dcb_num = dcb.next_cache
    
  def flush(self):
    if self.entries:
      for e in self.entries:
        e.flush()
    self.entries = None
    self.name_hash = None
  
  def ensure_entries(self):
    if not self.entries:
      self.read()
      
  def get_entries(self):
    self.ensure_entries()
    return self.entries
  
  def has_name(self, fn):
    fn_hash = fn.hash()
    fn_up = fn.to_upper()
    node_list = self.name_hash[fn_hash]
    for node in node_list:
      if node.name.to_upper() == fn_up:
        return True
    return False
  
  def blocks_create_new(self, free_blks, name, hash_chain_blk, parent_blk, meta_info):
    blk_num = free_blks[0]
    blkdev = self.blkdev
    # create a UserDirBlock
    ud = UserDirBlock(blkdev, blk_num)
    ud.create(parent_blk, name, meta_info.get_protect(), meta_info.get_comment(), meta_info.get_mod_ts(), hash_chain_blk)
    ud.write()    
    self.set_block(ud)
    self._init_name_hash()
    return blk_num
  
  def blocks_get_create_num(self):
    # the number of blocks needed for a new (empty) directory
    # -> only one UserDirBlock
    return 1
    
  def _create_node(self, node, name, meta_info):
    self.ensure_entries()
    
    # make sure a default meta_info is available
    if meta_info == None:
      meta_info = MetaInfo()
      meta_info.set_current_time()
      meta_info.set_default_protect()
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
    new_blk = node.blocks_create_new(free_blks, name, hash_chain_blk, self.block.blk_num, meta_info)

    # update my dir
    self.block.hash_table[fn_hash] = new_blk 
    self.block.write()
    
    # add node
    self.name_hash[fn_hash].insert(0,node)
    self.entries.append(node)
        
  def create_dir(self, name, meta_info=None):
    node = ADFSDir(self.volume, self)
    self._create_node(node, name, meta_info)
    return node
  
  def create_file(self, name, data, meta_info=None):
    node = ADFSFile(self.volume, self) 
    node.set_file_data(data)
    self._create_node(node, name, meta_info) 
    return node
  
  def _delete(self, node, wipe=False):
    self.ensure_entries()
    
    # can we delete?
    if not node.can_delete():
      raise FSError(DELETE_NOT_ALLOWED, node=node)
    # make sure its a node of mine
    if node.parent != self:
      raise FSError(INTERNAL_ERROR, node=node)
    if node not in self.entries:
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
    self.ensure_entries()
    return len(self.entries) == 0
  
  def delete_children(self, wipe, all):
    self.ensure_entries()
    entries = self.entries[:]
    for e in entries:
      e.delete(wipe, all)

  def get_entries_sorted_by_name(self):
    self.ensure_entries()
    return sorted(self.entries, key=lambda x : x.name.to_upper())
    
  def list(self, indent=0, all=False):
    ADFSNode.list(self, indent, all)
    if not all and indent > 0:
      return
    self.ensure_entries()
    es = self.get_entries_sorted_by_name()
    for e in es:
      e.list(indent=indent+1, all=all)
    
  def get_path(self, pc, allow_file=True, allow_dir=True):
    if len(pc) == 0:
      return self
    self.ensure_entries()
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
    bm[blk_num] = 'D'
    if show_all:
      self.ensure_entries()
      for e in self.entries:
        e.draw_on_bitmap(bm, True)

  def get_block_nums(self):
    self.ensure_entries()
    result = [self.block.blk_num]
    if self.volume.is_dircache:
      for dcb in self.dcache_blks:
        result.append(dcb.blk_num)
    return result

  def get_blocks(self, with_data=False):
    self.ensure_entries()
    result = [self.block]
    if self.volume.is_dircache:
      result += self.dcache_blks
    return result

  def get_size(self):
    return 0
  
  def get_size_str(self):
    return "DIR"
