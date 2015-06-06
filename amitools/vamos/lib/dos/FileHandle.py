import os
from DosStruct import FileHandleDef

class FileHandle:
  """represent an AmigaOS file handle (FH) in vamos"""

  def __init__(self, obj, ami_path, sys_path, need_close=True):
    self.obj = obj
    self.name = os.path.basename(sys_path)
    self.ami_path = ami_path
    self.sys_path = sys_path
    self.b_addr = 0
    self.need_close = need_close

  def __str__(self):
    return "[FH:'%s'(ami='%s',sys='%s',nc=%s)@%06x=B@%06x]" % (self.name, self.ami_path, self.sys_path, self.need_close, self.mem.addr, self.b_addr)

  def close(self):
    if self.need_close:
      self.obj.close()

  def alloc_fh(self, alloc, fs_handler_port):
    name = "File:" + self.name
    self.mem = alloc.alloc_struct(name, FileHandleDef)
    self.b_addr = self.mem.addr >> 2
    # -- fill filehandle
    # use baddr of FH itself as identifier
    self.mem.access.w_s("fh_Args", self.b_addr)
    # set port
    self.mem.access.w_s("fh_Type", fs_handler_port)
    return self.b_addr

  def free_fh(self, alloc):
    alloc.free_struct(self.mem)
