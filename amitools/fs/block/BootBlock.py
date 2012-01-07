from Block import Block

class BootBlock(Block):
  # raw dos types
  DOS0 = 0x444f5300
  DOS1 = 0x444f5301
  DOS2 = 0x444f5302
  DOS3 = 0x444f5303
  DOS4 = 0x444f5304
  DOS5 = 0x444f5305
  # more convenient dos type
  DOS_OFS = DOS0
  DOS_FFS = DOS1
  DOS_OFS_INTL = DOS2
  DOS_FFS_INTL = DOS3
  DOS_OFS_INTL_DIRCACHE = DOS4
  DOS_FFS_INTL_DIRCACHE = DOS5
  # string names for dos types
  dos_type_names = [
      'ofs',
      'ffs',
      'ofs+intl',
      'ffs+intl',
      'ofs+intl+dircache',
      'ffs+intl+dircache',
      'N/A',
      'N/A'
  ]
  
  DOS_MASK_FFS = 1
  DOS_MASK_INTL = 2
  DOS_MASK_DIRCACHE = 4
  
  def __init__(self, blkdev, blk_num=0):
    Block.__init__(self, blkdev, blk_num)
    self.dos_type = None
    self.got_root_blk = None
    self.got_chksum = 0
    self.calc_chksum = 0
    self.boot_code = None
  
  def create(self, dos_type=DOS0, root_blk=None, boot_code=None):
    Block.create(self)
    self._create_data()
    self.dos_type = dos_type
    self.calc_root_blk = int(self.blkdev.num_blocks / 2)
    if root_blk != None:
      self.got_root_blk = root_blk
    else:
      self.got_root_blk = self.calc_root_blk
    self.boot_code = boot_code
    self.valid_dos_type = True
    self.valid = True
  
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
    else:
      self.calc_chksum = 0
    self._write_data()
  
  def get_dos_type_flags(self):
    return self.dos_type & 0x7
  
  def get_dos_type_str(self):
    return self.dos_type_names[self.get_dos_type_flags()]
    
  def is_ffs(self):
    t = self.get_dos_type_flags()
    return (t & self.DOS_MASK_FFS) == self.DOS_MASK_FFS
  
  def is_intl(self):
    t = self.get_dos_type_flags()
    return self.is_dircache() or (t & self.DOS_MASK_INTL) == self.DOS_MASK_INTL
  
  def is_dircache(self):
    t = self.get_dos_type_flags()
    return (t & self.DOS_MASK_DIRCACHE) == self.DOS_MASK_DIRCACHE
  
  def dump(self):
    print "BootBlock(%d):" % self.blk_num
    print " dos_type:  0x%08x %s (valid: %s) is_ffs=%s is_intl=%s is_dircache=%s" \
      % (self.dos_type, self.get_dos_type_str(), self.valid_dos_type, self.is_ffs(), self.is_intl(), self.is_dircache())
    print " root_blk:  %d (got %d)" % (self.calc_root_blk, self.got_root_blk)
    print " chksum:    0x%08x (got) 0x%08x (calc)" % (self.got_chksum, self.calc_chksum)
    print " valid:     %s" % self.valid
