from ..block.rdb.RDBlock import *
from ..block.rdb.PartitionBlock import *
from FileSystem import FileSystem
from ..blkdev.PartBlockDevice import PartBlockDevice

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
  
  # ----- query -----
  
  def get_info(self):
    res = []
    pd = self.rdb.phy_drv
    res.append("PhysicalDisk: cyls=%d, heads=%d, secs=%d" % (pd.cyls, pd.heads, pd.secs))
    ld = self.rdb.log_drv
    res.append("LogicalDisk:  rdb_blks=[%d:%d], cyls=[%d:%d], cyl_blks=%d" % (ld.rdb_blk_lo, ld.rdb_blk_hi, ld.lo_cyl, ld.hi_cyl, ld.cyl_blks))
    # add partitions
    num = 0
    for p in self.parts:
      de = p.dos_env
      name = "'%s'" % p.drv_name
      extra = ""
      flags = p.flags
      if flags & PartitionBlock.FLAG_BOOTABLE == PartitionBlock.FLAG_BOOTABLE:
        extra += " bootable"
      if flags & PartitionBlock.FLAG_NO_AUTOMOUNT == PartitionBlock.FLAG_NO_AUTOMOUNT:
        extra += " no_automount"
      res.append("Partition: #%d %-06s cyls=[%8d:%8d] boot_pri=%d %s" % (num, name, de.low_cyl, de.high_cyl, de.boot_pri, extra))
      num += 1
    return res

  def get_num_partitions(self):
    return len(self.parts)
  
  def get_partition_blkdev(self, num):
    return PartBlockDevice(self.rawblk, self.parts[num])

  def find_partition_by_device_name(self, name):
    lo_name = name.lower()
    num = 0
    for p in self.parts:
      drv_name = p.drv_name.lower()
      if drv_name == lo_name:
        return num
      num += 1
    return None

      
    
