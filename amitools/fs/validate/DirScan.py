from BlockScan import BlockScan
from amitools.fs.FSString import FSString
from amitools.fs.FileName import FileName

class DirChainEntry:
  def __init__(self, blk_info):
    self.blk_info = blk_info
    self.parent_ok = False
    self.fn_hash_ok = False
    self.valid = False
    self.end = False
    self.orphaned = False
    
  def __str__(self):
    l = []
    if self.parent_ok:
      l.append("parent_ok")
    if self.fn_hash_ok:
      l.append("fn_hash_ok")
    if self.valid:
      l.append("valid")
    if self.end:
      l.append("end")
    if self.orphaned:
      l.append("orphaned")
    return "[DCE @%d '%s': %s]" % \
      (self.blk_info.blk_num, self.blk_info.name, " ".join(l))

class DirChain:
  def __init__(self, hash_val):
    self.hash_val = hash_val
    self.chain = []
  
  def add(self, dce):
    self.chain.append(dce)
    
  def get_entries(self):
    return self.chain
  
  def __str__(self):
    return "{DirChain +%d: #%d}" % (self.hash_val, len(self.chain))
    
class DirInfo:
  def __init__(self, blk_info):
    self.blk_info = blk_info
    self.chains = {}

  def add(self, dc):
    self.chains[dc.hash_val] = dc
    
  def get(self, hash_val):
    if hash_val in self.chains:
      return self.chains[hash_val]
    else:
      return None
  
  def get_chains(self):
    return self.chains
  
  def __str__(self):
    return "<DirInfo @%d '%s' #%d>" % (self.blk_info.blk_num, self.blk_info.name, len(self.chains))

class DirScan:
  def __init__(self, block_scan, log):
    self.log = log
    self.block_scan = block_scan
    self.dir_infos = None
  
  def scan(self):
    """check all directories"""
    # scan root/user dir(s)
    dirs = self.block_scan.get_blocks_of_type(BlockScan.BT_ROOT)
    dirs += self.block_scan.get_blocks_of_type(BlockScan.BT_DIR)
    dir_infos = []
    for bi in dirs:
      di = self.scan_dir(bi)
      dir_infos.append(di)
    self.dir_infos = dir_infos
  
  def get_dir_infos(self):
    return self.dir_infos
  
  def scan_dir(self, dir_bi):    
    """check a directory by scanning through the hash table entries and follow the chains
       Returns (all_chains_ok, dir_obj)
    """
    # get all potential child blocks
    child_blks = self.block_scan.get_blocks_with_key_value('parent_blk', dir_bi.blk_num)
    
    di = DirInfo(dir_bi)
    
    # run through hash_table of directory and build chains
    chains = {}
    hash_val = 0
    for blk_num in dir_bi.hash_table:
      if blk_num != 0:
        # build chain
        chain = DirChain(hash_val)
        self.build_chain(chain, dir_bi, blk_num, child_blks)
        di.add(chain)
      hash_val += 1
      
    # are there orphaned blocks with this dir as parent?
    num_orphaned = len(child_blks)
    if num_orphaned > 0:  
      self.log.msg(Log.INFO, "%d orphaned children of dir '%s' (%d)" % (num_orphaned, dir_bi.name, dir_bi.blk_num))
    
    # sort in orphaned entries
    for b in child_blks:
      # calc hash of name
      name = b.name
      fn = FileName(name)
      fn_hash = fn.hash()
      # get chain
      chain = di.get(fn_hash)
      if chain == None:
        chain = DirChain(hash_val)
        di.add(chain)
      # add dir chain entry
      dce = DirChainEntry(b)
      dce.orphaned = True
      chain.add(dce)
    
    return di
    
  def build_chain(self, chain, dir_blk_info, blk_num, child_blks):
    """build a block chain"""
    dir_blk_num = dir_blk_info.blk_num
    dir_name = dir_blk_info.name
    hash_val = chain.hash_val
    
    # remove block from child_blks
    for b in child_blks:
      if b.blk_num == blk_num:
        child_blks.remove(b)
    
    # get entry block
    blk_info = self.block_scan.get_block(blk_num)

    # create dir chain entry
    dce = DirChainEntry(blk_info)
    chain.add(dce)

    # not a block in range
    if blk_info == None:
      self.log.msg(Log.ERROR, "out-of-range block terminates chain #%d of dir '%s' (%d)" % (hash_val, dir_name, dir_blk_num), blk_num)
      dce.end = True
      return
    
    # check type of entry block
    b_type = blk_info.blk_type
    if b_type not in (BlockScan.BT_DIR, BlockScan.BT_FILE_HDR):
      self.log.msg(Log.ERROR, "invalid block terminates chain #%d of dir '%s' (%d)" % (hash_val, dir_name, dir_blk_num), blk_num)
      dce.end = True
      return
    
    # all following are ok
    dce.valid = True
     
    # check parent of block
    name = blk_info.name
    dce.parent_ok = (blk_info.parent_blk == dir_blk_num)
    if not dce.parent_ok:
      self.log.msg(Log.ERROR, "invalid parent in '%s' chain #%d of dir '%s' (%d)" % (name, hash_val, dir_name, dir_blk_num), blk_num)

    # check name hash
    fn = FileName(name)
    fn_hash = fn.hash()
    dce.fn_hash_ok = (fn_hash == hash_val)
    if not dce.fn_hash_ok:
      self.log.msg(Log.ERROR, "invalid name hash in '%s' chain #%d of dir '%s' (%d)" % (name, hash_val, dir_name, dir_blk_num), blk_num)      

    # check next block in chain
    next_blk = blk_info.next_blk
    if next_blk != 0:
      return self.build_chain(chain, dir_blk_info, next_blk, child_blks)
    else:
      dce.end = True
      return True
      
  def dump(self):
    for di in self.dir_infos:
      print di
      for hash_value in sorted(di.get_chains().keys()):
        dc = di.get(hash_value)
        print "  ",dc
        for dce in dc.get_entries():
          print "    ",dce
