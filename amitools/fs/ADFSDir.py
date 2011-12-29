import struct
from Block import Block
from UserDirBlock import UserDirBlock
from FileHeaderBlock import FileHeaderBlock
from ADFSFile import ADFSFile

class ADFSDir:
  def __init__(self, volume, block, is_vol=False):
    self.volume = volume
    self.block = block
    self.is_vol = is_vol
    self.blkdev = block.blkdev
    self.block_bytes = self.blkdev.block_bytes
    self.entries = None
    self.valid = False
    self.invalid_blocks = []
    
  def __repr__(self):
    return "[Dir(%d)'%s':%s,errs=%s]" % (self.block.blk_num, self.block.name, self.entries, self.invalid_blocks)
  
  def read(self, recursive=True):
    self.entries = []
    self.valid = False
    self.invalid_blocks = []
    self.name = self.block.name
    # run through hash table
    blocks = self.block.hash_table[:]    
    for blk_num in blocks:
      if blk_num != 0:
        # read anonymous block
        blk = Block(self.blkdev, blk_num)
        blk.read()
        ok = False
        if blk.valid_chksum and blk.type == Block.T_SHORT:
          # its a userdir
          if blk.sub_type == Block.ST_USERDIR:
            user_dir_blk = UserDirBlock(self.blkdev, blk_num)
            user_dir_blk.set(blk.data)
            if user_dir_blk.valid:
              user_dir = ADFSDir(self.volume, user_dir_blk)
              if recursive:
                ok = user_dir.read()
              else:
                ok = True
              self.entries.append(user_dir)
              # more in chain?
              hash_chain = user_dir_blk.hash_chain
              if hash_chain != 0:
                blocks.append(hash_chain)
          # its a file
          elif blk.sub_type == Block.ST_FILE:
            file_hdr_blk = FileHeaderBlock(self.blkdev, blk_num)
            file_hdr_blk.set(blk.data)
            if file_hdr_blk.valid:
              afile = ADFSFile(self.volume, file_hdr_blk)
              ok = afile.scan()
              self.entries.append(afile)
              # more in chain?
              hash_chain = file_hdr_blk.hash_chain
              if hash_chain != 0:
                blocks.append(hash_chain)
            
        if not ok:
          self.invalid_blocks.append(blk_num)
    self.valid = len(self.invalid_blocks) == 0
    return self.valid
  
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
      if e.name.lower() == pc[0]:
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
