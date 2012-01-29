from ..block.rdb.RDBlock import *
from ..block.rdb.PartitionBlock import *

class RDisk:
  def __init__(self, rawblk):
    self.rawblk = rawblk
    self.valid = False
    self.rdb = None
    self.parts = []

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
    return True
  
  def close(self):
    pass
    
  def dump(self):
    if self.rdb != None:
      self.rdb.dump()
    for p in self.parts:
      p.dump()
