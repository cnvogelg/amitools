from BlockDevice import BlockDevice
import os.path
import os

class PartBlockDevice(BlockDevice):
  def __init__(self, raw_blkdev, part_blk, auto_close=False):
    self.raw_blkdev = raw_blkdev
    self.part_blk = part_blk
    self.blk_off = 0
    self.auto_close = auto_close

  def open(self):
    # extract geometry from partition block
    dos_env = self.part_blk.dos_env
    lo_cyl = dos_env.low_cyl
    hi_cyl = dos_env.high_cyl
    cyls = hi_cyl - lo_cyl + 1
    heads = dos_env.surfaces
    secs = dos_env.blk_per_trk
    block_bytes = dos_env.block_size * 4
    reserved = dos_env.reserved
    boot_blocks = dos_env.boot_blocks
    if boot_blocks == 0:
      boot_blocks = 2
    self._set_geometry(cyls, heads, secs, block_bytes, reserved, boot_blocks)
    # calc block offset of partition
    self.blk_off = heads * secs * lo_cyl
    return True

  def flush(self):
    self.raw_blkdev.flush()

  def close(self):
    # auto close containing rdisk
    if self.auto_close:
      self.raw_blkdev.close()

  def read_block(self, blk_num):
    if blk_num >= self.num_blocks:
      raise ValueError("Invalid Part block num: got %d but max is %d" % (blk_num, self.num_blocks))
    return self.raw_blkdev.read_block(self.blk_off + blk_num)

  def write_block(self, blk_num, data):
    if blk_num >= self.num_blocks:
      raise ValueError("Invalid Part block num: got %d but max is %d" % (blk_num, self.num_blocks))
    if len(data) != self.block_bytes:
      raise ValueError("Invalid Part block size written: got %d but size is %d" % (len(data), self.block_bytes))
    self.raw_blkdev.write_block(self.blk_off + blk_num, data)
