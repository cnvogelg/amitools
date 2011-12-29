from Block import Block

class BootBlock(Block):
  DOS0 = 0x444f5300
  DOS5 = 0x444f5305
  
  def __init__(self, blkdev, blk_num=0):
    Block.__init__(self, blkdev, blk_num)
    self.dos_type = None
    self.root_blk = None
    self.got_chksum = None
    self.boot_code = None
  
  def create(self, dos_type, root_blk, boot_code=None):
    self._create_data()
    self.dos_type = dos_type
    self.root_blk = root_blk
    self.boot_code = boot_code
  
  def _calc_chksum(self):
    n = self.blkdev.block_longs
    chksum = 0
    for i in xrange(n):
      if i != 1: # skip chksum
        chksum += self._get_long(i)
        if chksum > 0xffffffff:
          chksum += 1
          chksum &= 0xffffffff
    return (~chksum) & 0xffffffff
  
  def read(self):
    self._read_data()
    self.dos_type = self._get_long(0)
    self.got_chksum = self._get_long(1)
    self.root_blk = self._get_long(2)
    self.calc_chksum = self._calc_chksum()
    self.boot_code = self.data[12:]
    # check validity
    self.valid_chksum = self.got_chksum == self.calc_chksum
    self.valid_dos_type = (self.dos_type >= self.DOS0) or (self.dos_type <= self.DOS5)
    self.valid_root_blk = (self.root_blk > 0) and (self.root_blk < self.blkdev.num_blocks)
    self.valid = self.valid_chksum and self.valid_dos_type and self.valid_root_blk
    return self.valid
  
  def write(self):
    self._create_data()
    self._put_long(0, dos_type)
    self._put_long(2, root_blk)
    if boot_code != None:
      n = len(boot_code)
      self.data[12:12+n] = boot_code
    self.calc_chksum = self._calc_chksum()
    self._put_long(1, self.calc_chksum)
  
  def dump(self):
    print "BootBlock(%d):" % self.blk_num
    print " dos_type:  0x%08x (valid: %s)" % (self.dos_type, self.valid_dos_type)
    print " root_blk:  %s (valid: %s)" % (self.root_blk, self.valid_root_blk)
    print " chksum:    0x%08x (got) 0x%08x (calc)" % (self.got_chksum, self.calc_chksum)
    print " boot_code: %d bytes" % len(self.boot_code)
    print " valid:     %s" % self.valid
