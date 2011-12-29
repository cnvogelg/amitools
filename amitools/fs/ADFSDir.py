import struct
from Block import Block
from UserDirBlock import UserDirBlock
from FileHeaderBlock import FileHeaderBlock
from ADFSFile import ADFSFile

class ADFSDir:
  def __init__(self, block):
    self.block = block
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
              user_dir = ADFSDir(user_dir_blk)
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
              afile = ADFSFile(file_hdr_blk)
              ok = afile.scan()
              # TEST:
              afile.read()
              self.entries.append(afile)
              # more in chain?
              hash_chain = file_hdr_blk.hash_chain
              if hash_chain != 0:
                blocks.append(hash_chain)
            
        if not ok:
          self.invalid_blocks.append(blk_num)
    self.valid = len(self.invalid_blocks) == 0
    return self.valid
  
  def dump(self):
    print "Dir(%d)" % self.block.blk_num
    print " entries: %s" % self.entries
    print " invalid blocks: %s" % self.invalid_blocks
  
  def list(self, indent=0):
    print " " * indent,"%-30s  ----DIR-  %s" % (self.block.name, self.block.mod_ts)
    if self.entries:
      for e in self.entries:
        e.list(indent=indent+1)
    