from amitools.fs.block.BootBlock import BootBlock
from amitools.fs.block.RootBlock import RootBlock

from amitools.fs.validate.Log import Log
from amitools.fs.validate.BlockScan import BlockScan
from amitools.fs.validate.DirScan import DirScan

class Validator:
  """Validate an AmigaDOS file system"""
    
  def __init__(self, blkdev, debug=True):
    self.log = Log(debug=debug)
    self.debug = debug
    self.blkdev = blkdev
    self.boot = None
    self.root = None
    self.block_scan = None

  def scan_boot(self):
    """Stage 1: scan boot block.
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
        self.log.msg(Log.WARN,"invalid boot block checksum",0)
      return True
    else:
      self.log.msg(Log.WARN,"invalid boot block dos type",0)
      return False
  
  def scan_root(self):
    """Stage 2: scan root block.
       Try to determine root block from boot block or guess number.
       Returns True if the root block could be decoded.
    """
    if self.boot != None:
      # retrieve root block number from boot block
      root_blk_num = self.boot.got_root_blk
      # check root block number
      if root_blk_num < self.blkdev.reserved or root_blk_num > self.blkdev.num_blocks:
        root_blk_num = self.blkdev.num_blocks / 2
        self.log.msg(Log.WARN,"Invalid root block number: using guess",root_blk_num)
    else:
      # guess root block number
      root_blk_num = self.blkdev.num_blocks / 2
      self.log.msg(Log.INFO,"Guessed root block number",root_blk_num)
    # read root block
    root = RootBlock(self.blkdev, root_blk_num)
    root.read()
    if not root.valid:
      self.log.msg(Log.ERROR,"Root block is not valid",root_blk_num)      
      self.root = None # mode without root
      return False
    else:
      self.root = root
      return True
  
  def scan_blocks(self, progress=lambda x : x):
    """Stage 3: full block scan.
       Return true if there is a chance of finding a file system on this block device.
    """
    self.block_scan = BlockScan(self.blkdev, self.log)
    self.block_scan.scan(progress=progress)
    if self.debug:
      self.block_scan.dump()
    return self.block_scan.any_chance_of_fs()

  def scan_dirs(self):
    """Stage 4: scan through all found directories"""
    self.dir_scan = DirScan(self.block_scan, self.log)
    self.dir_scan.scan()
    if self.debug:
      self.dir_scan.dump()
