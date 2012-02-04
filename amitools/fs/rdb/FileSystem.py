from ..block.rdb.FSHeaderBlock import *
from ..block.rdb.LoadSegBlock import *
from amitools.util.HexDump import *

class FileSystem:
  def __init__(self, blkdev, blk_num):
    self.blkdev = blkdev
    self.blk_num = blk_num
    self.fshd = None
    self.valid = False
    self.lsegs = []
    self.data = None
  
  def get_next_fs_blk(self):
    if self.fshd != None:
      return self.fshd.next
    else:
      return 0xffffffff

  def get_highest_blk_num(self):
    hi = self.blk_num
    for ls in self.lsegs:
      if ls.blk_num > hi:
        hi = ls.blk_num
    return hi

  def read(self):
    # read fs header
    self.fshd = FSHeaderBlock(self.blkdev, self.blk_num)
    if not self.fshd.read():
      self.valid = False
      return False
    # read lseg blocks
    lseg_blk = self.fshd.dev_node.seg_list_blk
    self.lsegs = []
    data = ""
    while lseg_blk != 0xffffffff:
      ls = LoadSegBlock(self.blkdev, lseg_blk)
      if not ls.read():
        self.valid = False
        return False
      lseg_blk = ls.next
      data += ls.get_data()
      self.lsegs.append(ls)
    self.data = data
    return True
  
  def get_data(self):
    return self.data
  
  def dump(self, hex_dump=False):
    if self.fshd != None:
      self.fshd.dump()
    # only dump ids of lseg blocks
    print "LoadSegBlocks:"
    ids = []
    for ls in self.lsegs:
      ids.append(str(ls.blk_num))
    print " lseg blks:  %s" % ",".join(ids)
    print " data size:  %d" % len(self.data)
    if hex_dump:
      print_hex(self.data)
