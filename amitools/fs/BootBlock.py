from Block import Block

class BootBlock(Block):
  DOS0 = 0x444f5300
  DOS5 = 0x444f5305
  
  def __init__(self, blkdev, blk_num=0):
    Block.__init__(self, blkdev, blk_num)
    self.dos_type = None
    self.got_root_blk = None
    self.got_chksum = None
    self.boot_code = None
  
  def create(self, dos_type=DOS0, root_blk=None, boot_code=None):
    self._create_data()
    self.dos_type = dos_type
    self.calc_root_blk = int(self.blkdev.num_blocks / 2)
    if root_blk != None:
      self.got_root_blk = root_blk
    else:
      self.got_root_blk = self.calc_root_blk
    self.boot_code = boot_code
    self.valid = True
    return True
  
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
    self.got_root_blk = self._get_long(2)
    self.calc_chksum = self._calc_chksum()
    # calc position of root block
    self.calc_root_blk = int(self.blkdev.num_blocks / 2)
    # check validity
    self.valid_chksum = self.got_chksum == self.calc_chksum
    self.valid_dos_type = (self.dos_type >= self.DOS0) or (self.dos_type <= self.DOS5)
    self.valid = self.valid_dos_type
    return self.valid
  
  def write(self):
    self._create_data()
    self._put_long(0, self.dos_type)
    self._put_long(2, self.got_root_blk)
    if self.boot_code != None:
      n = len(self.boot_code)
      self.data[12:12+n] = boot_code
      self.calc_chksum = self._calc_chksum()
      self._put_long(1, self.calc_chksum)
    self._write_data()
  
  def dump(self):
    print "BootBlock(%d):" % self.blk_num
    print " dos_type:  0x%08x (valid: %s)" % (self.dos_type, self.valid_dos_type)
    print " root_blk:  %d (got %d)" % (self.calc_root_blk, self.got_root_blk)
    print " chksum:    0x%08x (got) 0x%08x (calc)" % (self.got_chksum, self.calc_chksum)
    print " valid:     %s" % self.valid
