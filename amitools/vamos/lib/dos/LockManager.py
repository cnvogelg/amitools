import os.path
import logging

from amitools.vamos.Log import log_lock
from amitools.vamos.label.LabelRange import LabelRange
from amitools.vamos.Exceptions import *
from amitools.vamos.AccessStruct import AccessStruct
from DosStruct import *
from Error import *
from Lock import Lock

class LockManager:
  def __init__(self, path_mgr, dos_list, alloc, mem):
    self.path_mgr = path_mgr
    self.dos_list = dos_list
    self.alloc    = alloc
    self.mem      = mem
    self.locks_by_baddr = {}

  def generate_key(self, system_path):
    return os.lstat(system_path).st_ino

  def _register_lock(self, lock):
    # look up volume
    volume_name = self.path_mgr.ami_volume_of_path(lock.ami_path)
    log_lock.debug("fl_Volume: looking up volume '%s' of %s",volume_name,lock)
    volume = self.dos_list.get_entry_by_name(volume_name)
    if volume is None:
      vol_baddr = 0
      log_lock.warn("lock volume? volume=%s lock=%s",volume,lock)
    else:
      vol_baddr = volume.mem.addr
    # allocate lock struct
    b_addr = lock.alloc(self.alloc, vol_baddr, self.generate_key)
    self.locks_by_baddr[b_addr] = lock
    log_lock.info("registered: %s" % lock)

  def _unregister_lock(self, lock):
    log_lock.info("unregistered: %s" % lock)
    del self.locks_by_baddr[lock.b_addr]
    lock.free(self.alloc)
    del lock

  def create_lock(self, cur_dir, ami_path, exclusive):
    if ami_path == '':
      if cur_dir == None:
        ami_path = "SYS:"
      else:
        ami_path = cur_dir.ami_path
    else:
      ami_path = self.path_mgr.ami_abs_path(cur_dir,ami_path)
    sys_path = self.path_mgr.ami_to_sys_path(cur_dir,ami_path,searchMulti=True)
    name     = self.path_mgr.ami_name_of_path(cur_dir,ami_path)
    if sys_path == None:
      log_lock.info("lock '%s' invalid: no sys path found: '%s'", name, ami_path)
      return None
    exists = os.path.exists(sys_path)
    if not exists:
      log_lock.info("lock '%s' invalid: sys path does not exist: '%s' -> '%s'", name, ami_path, sys_path)
      return None
    lock = Lock(name, ami_path, sys_path, exclusive)
    self._register_lock(lock)
    return lock

  def dup_lock(self, lock):
    return self.create_lock(lock,"",False)

  def create_parent_lock(self, lock):
    # top level
    if lock.ami_path[-1] == ':':
      return None
    ami_path = lock.ami_path
    ami_parent_path = self.path_mgr.ami_abs_parent_path(ami_path)
    if ami_parent_path != ami_path:
      return self.create_lock(None,ami_parent_path, False)
    else:
      return None

  def get_by_b_addr(self, b_addr, none_if_missing=False):
    if b_addr == 0:
      return None
    elif b_addr in self.locks_by_baddr:
      lock = self.locks_by_baddr[b_addr]
      return lock
    else:
      if none_if_missing:
        return None
      else:
        raise VamosInternalError("Invalid File Lock at b@%06x" % b_addr)

  def release_lock(self, lock):
    if lock != None and lock.b_addr != 0:
      self._unregister_lock(lock)

  def volume_name_of_lock(self, lock):
    if lock == None:
      return "SYS:"
    else:
      vol_addr  = lock.mem.access.r_s("fl_Volume")
      volnode   = AccessStruct(self.mem,DosListVolumeDef,vol_addr)
      name_addr = volnode.r_s("dol_Name")
      name = self.mem.access.r_bstr(name_addr) + ":"
      return name
