from ..block.rdb.RDBlock import *
from ..block.rdb.PartitionBlock import *
from FileSystem import FileSystem
from ..blkdev.PartBlockDevice import PartBlockDevice
import amitools.util.ByteSize as ByteSize

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
    # physical disk info
    pd = self.rdb.phy_drv
    total_blks = self.get_total_blocks()
    total_bytes = self.get_total_bytes()
    extra="heads=%d sectors=%d" % (pd.heads, pd.secs)
    res.append("PhysicalDisk:        %8d %8d  %10d  %s  %s" \
      % (0, pd.cyls-1, total_blks, ByteSize.to_bi_str(total_bytes), extra))
    # logical disk info
    ld = self.rdb.log_drv
    extra="rdb_blks=[%d:%d] cyl_blks=%d" % (ld.rdb_blk_lo, ld.rdb_blk_hi, ld.cyl_blks)
    logic_blks = self.get_logical_blocks()
    logic_bytes = self.get_logical_bytes()
    res.append("LogicalDisk:         %8d %8d  %10d  %s  %s" \
      % (ld.lo_cyl, ld.hi_cyl, logic_blks, ByteSize.to_bi_str(logic_bytes), extra))
    # add partitions
    num = 0
    for p in self.parts:
      de = p.dos_env
      name = "'%s'" % p.drv_name
      extra = ""
      flags = p.flags
      if flags & PartitionBlock.FLAG_BOOTABLE == PartitionBlock.FLAG_BOOTABLE:
        extra += " bootable pri=%d" % de.boot_pri
      if flags & PartitionBlock.FLAG_NO_AUTOMOUNT == PartitionBlock.FLAG_NO_AUTOMOUNT:
        extra += " no_automount"
      part_blks = self.get_partition_blocks(num)
      part_bytes = self.get_partition_bytes(num)
      res.append("Partition: #%d %-06s %8d %8d  %10d  %s %s" \
        % (num, name, de.low_cyl, de.high_cyl, part_blks, ByteSize.to_bi_str(part_bytes), extra))
      num += 1
    return res

  def get_logical_blocks(self):
    ld = self.rdb.log_drv
    cyls = ld.hi_cyl - ld.lo_cyl + 1
    return cyls * ld.cyl_blks

  def get_logical_bytes(self, block_bytes=512):
    return self.get_logical_blocks() * block_bytes

  def get_total_blocks(self):
    pd = self.rdb.phy_drv
    return pd.cyls * pd.heads * pd.secs
  
  def get_total_bytes(self, block_bytes=512):
    return self.get_total_blocks() * block_bytes

  def get_num_partitions(self):
    return len(self.parts)
  
  def get_partition_blkdev(self, num):
    return PartBlockDevice(self.rawblk, self.parts[num])

  def get_partition_blocks(self, num):
    p = self.parts[num]
    cyls = p.dos_env.high_cyl - p.dos_env.low_cyl + 1
    ld = self.rdb.log_drv
    return cyls * ld.cyl_blks

  def get_partition_bytes(self, num, block_size=512):
    return self.get_partition_blocks(num) * block_size

  def find_partition_by_device_name(self, name):
    lo_name = name.lower()
    num = 0
    for p in self.parts:
      drv_name = p.drv_name.lower()
      if drv_name == lo_name:
        return num
      num += 1
    return None

      
    
