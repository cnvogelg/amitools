from amitools.fs.block.rdb.FSHeaderBlock import *
from amitools.fs.block.rdb.LoadSegBlock import *
from amitools.util.HexDump import *
import amitools.fs.DosType as DosType

class FileSystem:
  def __init__(self, blkdev, blk_num, num):
    self.blkdev = blkdev
    self.blk_num = blk_num
    self.num = num
    self.fshd = None
    self.valid = False
    self.lsegs = []
    self.data = None
  
  def get_next_fs_blk(self):
    if self.fshd != None:
      return self.fshd.next
    else:
      return 0xffffffff

  def get_blk_nums(self):
    res = [self.blk_num]
    for ls in self.lsegs:
      res.append(ls.blk_num)
    return res

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
  
  # ----- create ------

  def get_total_blocks(self, data):
    size = len(data)
    lseg_size = self.blkdev.block_bytes - 20
    num_lseg = int((size + lseg_size - 1)/lseg_size)
    return num_lseg + 1
    
  def create(self, blks, data, version, dos_type):
    self.data = data
    # create fs header
    self.fshd = FSHeaderBlock(self.blkdev, self.blk_num)
    self.fshd.create(version=version, dos_type=dos_type)
    # create lseg blocks
    self.lsegs = []
    lseg_size = self.blkdev.block_bytes - 20
    off = 0
    size = len(data)
    blk_off = 0
    self.fshd.dev_node.seg_list_blk = blks[blk_off]
    while(off < size):
      blk_len = size - off
      if blk_len > lseg_size:
        blk_len = lseg_size
      blk_data = data[off:off+blk_len]
      # create new lseg block
      ls = LoadSegBlock(self.blkdev, blks[blk_off])
      # get next block
      if blk_off == len(blks)-1:
        next = Block.no_blk
      else:
        next = blks[blk_off+1]
      ls.create(next=next)
      ls.set_data(blk_data)
      self.lsegs.append(ls)
      # next round
      off += blk_len
      blk_off += 1
    
  def write(self, only_fshd=False):
    self.fshd.write()
    if not only_fshd:
      for lseg in self.lsegs:
        lseg.write()
  
  # ----- query -----
  
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
  
  def get_flags_info(self):
    flags = self.fshd.get_flags()
    res = []
    for f in flags:
      res.append("%s=0x%x" % f)
    return " ".join(res)
  
  def get_valid_flag_names(self):
    return self.fshd.get_valid_flag_names()

  def get_info(self):
    flags = self.get_flags_info()
    return "FileSystem #%d %s version=%s size=%d %s" % (self.num, DosType.num_to_tag_str(self.fshd.dos_type), self.fshd.get_version_string(), len(self.data), flags)

  # ----- edit -----
  
  def clear_flags(self):
    self.fshd.patch_flags = 0
    self.fshd.write()
    return True
  
  def set_flags(self, flags, clear=False):
    if clear:
      self.fshd.patch_flags = 0
    self.fshd.set_flags(flags)
    self.fshd.write()
  