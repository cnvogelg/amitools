import os
import stat
import uuid

from amitools.vamos.Log import log_lock
from amitools.vamos.AccessStruct import AccessStruct

from DosStruct import FileLockDef, DateStampDef
from DosProtection import DosProtection
from AmiTime import *
from Error import *

class Lock:
  """represent an AmigaOS Lock in vamos"""

  def __init__(self, name, ami_path, sys_path, exclusive=False):
    self.ami_path = ami_path
    self.sys_path = sys_path
    self.name = name
    self.exclusive = exclusive
    self.mem = None
    self.b_addr  = 0
    self.key     = 0
    self.dirent  = None

  def __str__(self):
    addr = 0
    if self.mem is not None:
      addr = self.mem.addr
    return "[Lock:'%s'(ami='%s',sys='%s',key='%s',ex=%d)@%06x=b@%06x]" % (self.name, self.ami_path, self.sys_path, self.key, self.exclusive, addr, self.b_addr)

  def alloc(self, alloc, vol_addr,generate_key):
    self.keygen = generate_key
    self.key    = self.keygen(self.sys_path)
    name        = "Lock: %s" % self
    self.mem    = alloc.alloc_struct(name, FileLockDef)
    self.mem.access.w_s("fl_Key" ,self.key)
    self.b_addr = self.mem.addr >> 2
    return self.b_addr

  def free(self, alloc):
    alloc.free_struct(self.mem)

  # --- lock ops ---

  def examine_file(self, fib_mem, name, sys_path):
    # name
    name_addr = fib_mem.s_get_addr('fib_FileName')
    fib_mem.w_cstr(name_addr, name)
    # create the "inode" information
    key = self.keygen(sys_path)
    fib_mem.w_s('fib_DiskKey',key)
    # type
    if os.path.isdir(sys_path):
      dirEntryType = 2
    else:
      dirEntryType = (-3) & 0xffffffff
    fib_mem.w_s('fib_DirEntryType', dirEntryType )
    fib_mem.w_s('fib_EntryType',    dirEntryType )
    # protection
    prot = DosProtection(0)
    try:
      os_stat = os.stat(sys_path)
      mode = os_stat.st_mode
      if mode & stat.S_IXUSR == 0:
        prot.clr(DosProtection.FIBF_EXECUTE)
      if mode & stat.S_IRUSR == 0:
        prot.clr(DosProtection.FIBF_READ)
      if mode & stat.S_IWUSR == 0:
        prot.clr(DosProtection.FIBF_WRITE)
      log_lock.debug("examine lock: '%s' mode=%03o: prot=%s", name, mode, prot)
    except OSError:
      return ERROR_OBJECT_IN_USE
    fib_mem.w_s('fib_Protection', prot.mask)
    # size
    if os.path.isfile(sys_path):
      size = os.path.getsize(sys_path)
      fib_mem.w_s('fib_Size', size)
    # date (use mtime here)
    date_addr = fib_mem.s_get_addr('fib_Date')
    date = AccessStruct(fib_mem.mem, DateStampDef, date_addr)
    t = os.path.getmtime(sys_path)
    at = sys_to_ami_time(t)
    date.w_s('ds_Days', at.tday)
    date.w_s('ds_Minute', at.tmin)
    date.w_s('ds_Tick', at.tick)
    return NO_ERROR

  def examine_lock(self, fib_mem):
    return self.examine_file(fib_mem, self.name, self.sys_path)

  def examine_next(self, fib_mem):
    if self.dirent == None:
      dirEntryType = fib_mem.r_s('fib_DirEntryType')
      if os.path.isdir(self.sys_path):
        self.dirent = os.listdir(self.sys_path)
      else:
        self.dirent = []

    if len(self.dirent) > 0:
      aname = self.dirent[0]
      apath = self.sys_path + "/" + self.dirent[0]
      self.dirent = self.dirent[1:]
      return self.examine_file(fib_mem, aname, apath)

    self.dirent = None
    return ERROR_NO_MORE_ENTRIES

  def find_volume_node(self,dos_list):
    return self.mem.access.r_s("fl_Volume")
