from ..block.rdb.RDBlock import *
from ..block.rdb.PartitionBlock import *
from FileSystem import FileSystem

class RDisk:
  def __init__(self, rawblk):
    self.rawblk = rawblk
    self.valid = False
    self.rdb = None
    self.parts = []
    self.fs = []

  def open(self):
    # read RDB
    self.rdb = RDBlock(self.rawblk)
    if not self.rdb.read():
      self.valid = False
      return False
    # read partitions
    part_blk = self.rdb.part_list
    self.parts = []
    while part_blk != PartitionBlock.no_blk:
      pb = PartitionBlock(self.rawblk, part_blk)
      if not pb.read():
        self.valid = False
        return False
      self.parts.append(pb)
      part_blk = pb.next
    # read fs
    fs_blk = self.rdb.fs_list
    self.fs = []
    while fs_blk != PartitionBlock.no_blk:
      fs = FileSystem(self.rawblk, fs_blk)
      if not fs.read():
        self.valid = False
        return False
      self.fs.append(fs)
      fs_blk = fs.get_next_fs_blk()
    return True
  
  def close(self):
    pass
    
  def dump(self, hex_dump=False):
    # rdb
    if self.rdb != None:
      self.rdb.dump()
    # partitions
    for p in self.parts:
      p.dump()
    # fs
    for fs in self.fs:
      fs.dump(hex_dump)
