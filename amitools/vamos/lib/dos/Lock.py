from DosStruct import FileLockDef

class Lock:
  """represent an AmigaOS Lock in vamos"""

  def __init__(self, name, ami_path, sys_path, exclusive=False):
    self.ami_path = ami_path
    self.sys_path = sys_path
    self.name = name
    self.exclusive = exclusive
    self.mem = None
    self.b_addr = 0
    self.dirent = []

  def __str__(self):
    return "[Lock:'%s'(ami='%s',sys='%s',ex=%d)@%06x=b@%06x]" % (self.name, self.ami_path, self.sys_path, self.exclusive, self.mem.addr, self.b_addr)

  def alloc(self, alloc, vol_baddr):
    name = "Lock:" + self.name
    self.mem = alloc.alloc_struct(name, FileLockDef)
    self.mem.access.w_s("fl_Volume", vol_baddr)
    self.b_addr = self.mem.addr >> 2
    return self.b_addr

  def free(self, alloc):
    alloc.free_struct(self.mem)
