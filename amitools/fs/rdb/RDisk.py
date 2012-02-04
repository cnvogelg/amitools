from ..block.rdb.RDBlock import *
from ..block.rdb.PartitionBlock import *
from FileSystem import FileSystem
from ..blkdev.PartBlockDevice import PartBlockDevice
import amitools.util.ByteSize as ByteSize
import amitools.fs.DosType as DosType

class RDisk:
  def __init__(self, rawblk):
    self.rawblk = rawblk
    self.valid = False
    self.rdb = None
    self.parts = []
    self.fs = []
    self.hi_rdb_blk = 0

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
      # remember highest rdb block
      if part_blk > self.hi_rdb_blk:
        self.hi_rdb_blk = part_blk
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
      # remember highest rdb block
      hi = fs.get_highest_blk_num()
      if hi > self.hi_rdb_blk:
        self.hi_rdb_blk = hi
      fs_blk = fs.get_next_fs_blk()
    # TODO: add bad block blocks
    return True
  
  def create(self, disk_geo, rdb_cyl=1, hi_rdb_blk=0, disk_names=None, ctrl_names=None):
    cyls = disk_geo.cyls
    heads = disk_geo.heads
    secs = disk_geo.secs
    cyl_blks = heads * secs
    rdb_blk_hi = cyl_blks * rdb_cyl - 1
    
    if disk_names != None:
      disk_vendor = disk_names[0]
      disk_product = disk_names[1]
      disk_revision = disk_names[2]
    else:
      disk_vendor = 'RDBTOOL'
      disk_product = 'IMAGE'
      disk_revision = '2012'
      
    if ctrl_names != None:
      ctrl_vendor = ctrl_names[0]
      ctrl_product = ctrl_names[1]
      ctrl_revision = ctrl_names[2]
    else:
      ctrl_vendor = ''
      ctrl_product = ''
      ctrl_revision = ''
    
    flags = 0x7
    if disk_names != None:
      flags |= 0x10
    if ctrl_names != None:
      flags |= 0x20
    
    # create RDB
    phy_drv = RDBPhysicalDrive(cyls, heads, secs)
    log_drv = RDBLogicalDrive(rdb_blk_hi=rdb_blk_hi, lo_cyl=rdb_cyl, hi_cyl=cyls-1, cyl_blks=cyl_blks, high_rdsk_blk=hi_rdb_blk)
    drv_id = RDBDriveID(disk_vendor, disk_product, disk_revision, ctrl_vendor, ctrl_product, ctrl_revision)
    self.rdb = RDBlock(self.rawblk)
    self.rdb.create(phy_drv, log_drv, drv_id, flags=flags)
    self.rdb.write()
  
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
    extra="rdb_blks=[%d:%d,%d(%d)] cyl_blks=%d" % (ld.rdb_blk_lo, ld.rdb_blk_hi, ld.high_rdsk_blk, self.hi_rdb_blk, ld.cyl_blks)
    logic_blks = self.get_logical_blocks()
    logic_bytes = self.get_logical_bytes()
    res.append("LogicalDisk:         %8d %8d  %10d  %s  %s" \
      % (ld.lo_cyl, ld.hi_cyl, logic_blks, ByteSize.to_bi_str(logic_bytes), extra))
    # add partitions
    num = 0
    for p in self.parts:
      de = p.dos_env
      name = "'%s'" % p.drv_name
      extra = DosType.num_to_tag_str(p.dos_env.dos_type)
      flags = p.flags
      if flags & PartitionBlock.FLAG_BOOTABLE == PartitionBlock.FLAG_BOOTABLE:
        extra += " bootable pri=%d" % de.boot_pri
      if flags & PartitionBlock.FLAG_NO_AUTOMOUNT == PartitionBlock.FLAG_NO_AUTOMOUNT:
        extra += " no_automount"
      part_blks = self.get_partition_blocks(num)
      part_bytes = self.get_partition_bytes(num)
      res.append("Partition: #%d %-06s %8d %8d  %10d  %s  %s" \
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

  # ----- edit -----
  
  def check_cyl_range(self, lo_cyl, hi_cyl):
    if lo_cyl > hi_cyl:
      return False
    log_drv = self.rdb.log_drv
    if not (lo_cyl >= log_drv.lo_cyl and hi_cyl <= log_drv.hi_cyl):
      return False
    # check partitions
    for p in self.parts:
      lo = p.dos_env.low_cyl
      hi = p.dos_env.high_cyl
      if not ((hi_cyl < lo) or (lo_cyl > hi)):
        return False
    return True
  
  def has_free_rdb_blocks(self, num):
    return self.hi_rdb_blk + num <= self.rdb.log_drv.rdb_blk_hi
    
  def alloc_rdb_blocks(self, num):
    blk_num = self.hi_rdb_blk + 1
    self.hi_rdb_blk += num
    return blk_num
    
  def add_partition(self, drv_name, lo_cyl, hi_cyl, dev_flags=0, flags=0, dostype=DosType.DOS0):
    # cyl range is not free anymore or invalid
    if not self.check_cyl_range(lo_cyl, hi_cyl):
      return False
    # no space left for partition block
    if not self.has_free_rdb_blocks(1):
      return False
    # crete a new parttion block
    blk_num = self.alloc_rdb_blocks(1)
    pb = PartitionBlock(self.rawblk, blk_num)
    heads = self.rdb.phy_drv.heads
    blk_per_trk = self.rdb.phy_drv.secs
    dos_env = PartitionDosEnv(low_cyl=lo_cyl, high_cyl=hi_cyl, surfaces=heads, blk_per_trk=blk_per_trk)
    pb.create(drv_name, dos_env)
    pb.write()
    # link block
    if len(self.parts) == 0:
      # write into RDB
      self.rdb.part_list = blk_num
      self.rdb.write()
    else:
      # write into last partition block
      last_pb = self.parts[-1]
      last_pb.next = blk_num
      last_pb.write()
    # add to partition list
    self.parts.append(pb)
    return True
    
    
    
