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

    self.locks_by_key = {}

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
    self.locks_by_key[lock.key] = lock
    log_lock.info("registered: %s" % lock)

  def _unregister_lock(self, lock):
    if not self.locks_by_key.has_key(lock.key):
      raise VamosInternalError("Lock %s not registered!" % lock)
    check = self.locks_by_key[lock.key]
    if check != lock:
      raise VamosInternalError("Invalid Lock unregistered: %s" % lock)
    del self.locks_by_key[lock.key]
    log_lock.info("unregistered: %s" % lock)
    lock.b_addr = 0
    lock.addr = 0
    lock.free(self.alloc)

  def create_lock(self, ami_path, exclusive):
    if ami_path == '':
      ami_path = self.path_mgr.ami_abs_cur_path()
    else:
      ami_path = self.path_mgr.ami_abs_path(ami_path)
    sys_path = self.path_mgr.ami_to_sys_path(ami_path,searchMulti=True)
    name = self.path_mgr.ami_name_of_path(ami_path)
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

  def _get_key_from_baddr(self, b_addr):
    addr = b_addr << 2
    return self.mem.access.r32(addr + 4)

  def get_by_b_addr(self, b_addr, none_if_missing=False):
    # current dir lock
    if b_addr == 0:
      (cur_dev, cur_path) = self.path_mgr.get_cur_path()
      ami_path = cur_dev + ":" + cur_path
      sys_path = self.path_mgr.ami_to_sys_path(ami_path)
      return Lock("local",ami_path,sys_path)
    elif self.locks_by_key.has_key(self._get_key_from_baddr(b_addr)):
      lock = self.locks_by_key[self._get_key_from_baddr(b_addr)]
      return lock
    else:
      if none_if_missing:
        return None
      else:
        raise VamosInternalError("Invalid File Lock at b@%06x" % b_addr)

  def release_lock(self, lock):
    if lock.b_addr != 0:
      self._unregister_lock(lock)
