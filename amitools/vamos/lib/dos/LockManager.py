import os.path
import logging
import stat

from amitools.vamos.Log import log_lock
from amitools.vamos.label.LabelRange import LabelRange
from amitools.vamos.Exceptions import *
from amitools.vamos.AccessStruct import AccessStruct
from AmiTime import *
from DosStruct import *
from Error import *
from DosProtection import DosProtection

class AmiLock:
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


class LockManager:
  def __init__(self, path_mgr, dos_list, alloc):
    self.path_mgr = path_mgr
    self.dos_list = dos_list
    self.alloc = alloc

    self.locks_by_b_addr = {}

  def _register_lock(self, lock):
    # look up volume
    volume_name = self.path_mgr.ami_volume_of_path(lock.ami_path)
    log_lock.debug("fl_Volume: looking up volume '%s' of %s",volume_name,lock)
    volume = self.dos_list.get_entry_by_name(volume_name)
    if volume is None:
      vol_baddr = 0
      log_lock.warn("lock volume? volume=%s lock=%s",volume,lock)
    else:
      vol_baddr = volume.baddr
    # allocate lock struct
    b_addr = lock.alloc(self.alloc, vol_baddr)
    self.locks_by_b_addr[b_addr] = lock
    log_lock.info("registered: %s" % lock)

  def _unregister_lock(self, lock):
    if not self.locks_by_b_addr.has_key(lock.b_addr):
      raise VamosInternalError("Lock %s not registered!" % lock)
    check = self.locks_by_b_addr[lock.b_addr]
    if check != lock:
      raise VamosInternalError("Invalid Lock unregistered: %s" % lock)
    del self.locks_by_b_addr[lock.b_addr]
    log_lock.info("unregistered: %s" % lock)
    lock.b_addr = 0
    lock.addr = 0
    lock.free(self.alloc)

  def create_lock(self, ami_path, exclusive):
    if ami_path == '':
      ami_path = self.path_mgr.ami_abs_cur_path()
    else:
      ami_path = self.path_mgr.ami_abs_path(ami_path)
    sys_path = self.path_mgr.ami_to_sys_path(ami_path)
    name = self.path_mgr.ami_name_of_path(ami_path)
    if sys_path == None:
      log_lock.info("lock '%s' invalid: no sys path found: '%s'", name, ami_path)
      return None
    exists = os.path.exists(sys_path)
    if not exists:
      log_lock.info("lock '%s' invalid: sys path does not exist: '%s' -> '%s'", name, ami_path, sys_path)
      return None
    lock = AmiLock(name, ami_path, sys_path, exclusive)
    self._register_lock(lock)
    return lock

  def create_parent_lock(self, lock):
    # top level
    if lock.ami_path[-1] == ':':
      return None
    ami_path = lock.ami_path
    ami_parent_path = self.path_mgr.ami_abs_parent_path(ami_path)
    if ami_parent_path != ami_path:
      return self.create_lock(ami_parent_path, False)
    else:
      return None

  def get_by_b_addr(self, b_addr, none_if_missing=False):
    # current dir lock
    if b_addr == 0:
      (cur_dev, cur_path) = self.path_mgr.get_cur_path()
      ami_path = cur_dev + ":" + cur_path
      sys_path = self.path_mgr.ami_to_sys_path(ami_path)
      return AmiLock("local",ami_path,sys_path)
    elif self.locks_by_b_addr.has_key(b_addr):
      return self.locks_by_b_addr[b_addr]
    else:
      if none_if_missing:
        return None
      else:
        raise VamosInternalError("Invalid File Lock at b@%06x" % b_addr)

  def release_lock(self, lock):
    if lock.b_addr != 0:
      self._unregister_lock(lock)

  def examine_file(self, fib_mem, name, sys_path):
    # name
    name_addr = fib_mem.s_get_addr('fib_FileName')
    fib_mem.w_cstr(name_addr, name)
    # dummy key
    fib_mem.w_s('fib_DiskKey',0xcafebabe)
    # type
    if os.path.isdir(sys_path):
      dirEntryType = 0x2 # dir
    else:
      dirEntryType = 0xfffffffd # file
    fib_mem.w_s('fib_DirEntryType', dirEntryType )
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

  def examine_lock(self, lock, fib_mem):
    return self.examine_file(fib_mem, lock.name, lock.sys_path)

  def examine_next(self, lock, fib_mem):
    if lock.dirent == None:
      dirEntryType = fib_mem.r_s('fib_DirEntryType')
      if os.path.isdir(lock.sys_path):
        lock.dirent = os.listdir(lock.sys_path)
      else:
        lock.dirent = []

    if len(lock.dirent) > 0:
      aname = lock.dirent[0]
      apath = lock.sys_path + "/" + lock.dirent[0]
      lock.dirent = lock.dirent[1:len(lock.dirent)]
      return self.examine_file(fib_mem, aname, apath)

    lock.dirent = None
    return ERROR_NO_MORE_ENTRIES


