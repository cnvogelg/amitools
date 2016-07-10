from amitools.fs.block.rdb.PartitionBlock import *
from amitools.fs.blkdev.PartBlockDevice import PartBlockDevice
import amitools.util.ByteSize as ByteSize
import amitools.fs.DosType as DosType

class Partition:
  def __init__(self, blkdev, blk_num, num, cyl_blks, rdisk):
    self.blkdev = blkdev
    self.blk_num = blk_num
    self.num = num
    self.cyl_blks = cyl_blks
    self.rdisk = rdisk
    self.part_blk = None

  def get_next_partition_blk(self):
    if self.part_blk != None:
      return self.part_blk.next
    else:
      return 0xffffffff

  def get_blk_num(self):
    """return the block number of the partition block"""
    return self.blk_num

  def read(self):
    # read fs header
    self.part_blk = PartitionBlock(self.blkdev, self.blk_num)
    if not self.part_blk.read():
      self.valid = False
      return False
    self.valid = True
    return True

  def create_blkdev(self, auto_close_rdb_blkdev=False):
    """create a block device for accessing this partition"""
    return PartBlockDevice(self.blkdev, self.part_blk, auto_close_rdb_blkdev)

  def write(self):
    self.part_blk.write()

  # ----- Query -----

  def dump(self):
    self.part_blk.dump()

  def get_num_blocks(self):
    """return total number of blocks in this partition"""
    p = self.part_blk
    cyls = p.dos_env.high_cyl - p.dos_env.low_cyl + 1
    return cyls * self.cyl_blks

  def get_num_bytes(self, block_size=512):
    return self.get_num_blocks() * block_size

  def get_drive_name(self):
    return self.part_blk.drv_name

  def get_flags(self):
    return self.part_blk.flags

  def get_index(self):
    return self.num

  def get_cyl_range(self):
    de = self.part_blk.dos_env
    if de == None:
      return None
    else:
      return (de.low_cyl, de.high_cyl)

  def get_info(self, total_blks=0):
    """return a string line with typical info about this partition"""
    p = self.part_blk
    de = p.dos_env
    name = "'%s'" % p.drv_name
    part_blks = self.get_num_blocks()
    part_bytes = self.get_num_bytes()
    extra = ""
    if total_blks != 0:
      ratio = 100.0 * part_blks / total_blks
      extra += "%6.2f%%  " % ratio
    # add dos type
    dos_type = de.dos_type
    extra += DosType.num_to_tag_str(dos_type)
    extra += "/0x%04x" % dos_type
    # max transfer
    extra += " max_transfer=0x%x" % de.max_transfer
    extra += " mask=0x%x" % de.mask
    extra += " num_buffer=%d" % de.num_buffer
    # add flags
    flags = p.flags
    if flags & PartitionBlock.FLAG_BOOTABLE == PartitionBlock.FLAG_BOOTABLE:
      extra += " bootable pri=%d" % de.boot_pri
    if flags & PartitionBlock.FLAG_NO_AUTOMOUNT == PartitionBlock.FLAG_NO_AUTOMOUNT:
      extra += " no_automount"
    return "Partition: #%d %-06s %8d %8d  %10d  %s  %s" \
      % (self.num, name, de.low_cyl, de.high_cyl, part_blks, ByteSize.to_byte_size_str(part_bytes), extra)


