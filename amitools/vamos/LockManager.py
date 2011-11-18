import os.path
import logging

from Log import log_lock
from LabelRange import LabelRange
from Exceptions import *
from lib.dos.AmiTime import *
from lib.dos.DosStruct import *
from AccessStruct import AccessStruct

class AmiLock:
  def __init__(self, name, ami_path, sys_path, exclusive=False):
    self.ami_path = ami_path
    self.sys_path = sys_path
    self.name = name
    self.exclusive = exclusive
    self.addr = 0
    self.b_addr = 0
  def __str__(self):
    return "[Lock:'%s'(ami='%s',sys='%s',ex=%d)@%06x=b@%06x]" % (self.name, self.ami_path, self.sys_path, self.exclusive, self.addr, self.b_addr)

class LockManager(LabelRange):
  def __init__(self, path_mgr, doslist_mgr, base_addr, size):
    self.path_mgr = path_mgr
    self.doslist_mgr = doslist_mgr
    self.base_addr = base_addr
    self.cur_addr = base_addr
    log_lock.info("init manager: base=%06x" % self.base_addr)
    self.locks_by_b_addr = {}
    LabelRange.__init__(self, "locks", base_addr, size)
    self.lock_def  = FileLockDef
    self.lock_size = FileLockDef.get_size()
  
  # direct read access to lock structure
  def r32_lock(self, addr):
    # find out associated file handle
    rel = int((addr - self.base_addr) / self.lock_size)
    lock_addr = self.base_addr + rel * self.lock_size
    b_addr = lock_addr >> 2
    lock = self.get_by_b_addr(b_addr)
    if lock != None:
      # get addon text
      delta = addr - lock_addr
      name,off,val_type_name = self.lock_def.get_name_for_offset(delta, 2)
      type_name = self.lock_def.get_type_name()
      addon="%s+%d = %s(%s)+%d  %s" % (type_name, delta, name, val_type_name, off, lock)

      # get some special values
      val = 0
      # get DosList entry of associated volume
      if name == 'fl_Volume':
        ami_path = lock.ami_path
        volume_name = self.path_mgr.ami_volume_of_abspath(ami_path)
        log_lock.debug("fl_Volume: looking up volume '%s' of %s",volume_name,lock)
        volume = self.doslist_mgr.get_entry_by_name(volume_name)
        if volume == None:
          raise VamosInternalError("No DosList entry found for volume '%s'" % vol)
        val = volume.baddr
  
      self.trace_mem_int('R', 2, addr, val, text="LOCK", level=logging.INFO, addon=addon)
      return val
    else:
      self.trace_mem_int('R', 2, addr, val, text="NO_LOCK", level=logging.WARN)
      return 0
  
  def _register_lock(self, lock):
    addr = self.cur_addr
    self.cur_addr += 4
    lock.addr = addr
    lock.b_addr = addr >> 2
    self.locks_by_b_addr[lock.b_addr] = lock
    log_lock.info("registered: %s" % lock)
    
  def _unregister_lock(self, lock):
    check = self.locks_by_b_addr[lock.b_addr]
    if check != lock:
      raise VamosInternalError("Invalud Lock unregistered: %s" % lock)
    del self.locks_by_b_addr[lock.b_addr]
    log_lock.info("unregistered: %s" % lock)
    lock.b_addr = 0
    lock.addr = 0
  
  def create_lock(self, ami_path, exclusive):
    if ami_path == '':
      ami_path = self.path_mgr.ami_abs_cur_path()
    else:
      ami_path = self.path_mgr.ami_abs_path(ami_path)
    sys_path = self.path_mgr.ami_to_sys_path(ami_path)
    if sys_path == None:
      log_lock.info("lock not found: '%s'" % ami_path)
      return None
    exists = os.path.exists(sys_path)
    if not exists:
      log_lock.info("lock not found: '%s' -> '%s'" % (ami_path, sys_path))
      return None      
    name = self.path_mgr.ami_name_of_path(ami_path)
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
    
  def get_by_b_addr(self, b_addr):
    # current dir lock
    if b_addr == 0:
      (cur_dev, cur_path) = self.path_mgr.get_cur_path()
      ami_path = cur_dev + ":" + cur_path
      sys_path = self.path_mgr.ami_to_sys_path(ami_path)
      return AmiLock("local",ami_path,sys_path)
    elif self.locks_by_b_addr.has_key(b_addr):
      return self.locks_by_b_addr[b_addr]
    else:
      raise VamosInternalError("Invalid File Lock at b@%06x" % b_addr)
  
  def release_lock(self, lock):
    self._unregister_lock(lock)

  def examine_lock(self, lock, fib_mem):
    # name
    name_addr = fib_mem.s_get_addr('fib_FileName')
    fib_mem.w_cstr(name_addr, lock.name)
    # dummy key
    fib_mem.w_s('fib_DiskKey',0xcafebabe)
    # type
    if os.path.isdir(lock.sys_path):
      dirEntryType = 0x2 # dir
    else:
      dirEntryType = 0xfffffffd # file
    fib_mem.w_s('fib_DirEntryType', dirEntryType )
    # protection
    prot = 0xf
    fib_mem.w_s('fib_Protection', prot)
    # size
    if os.path.isfile(lock.sys_path):
      size = os.path.getsize(lock.sys_path)
      fib_mem.w_s('fib_Size', size)
    # date (use mtime here)
    date_addr = fib_mem.s_get_addr('fib_Date')
    date = AccessStruct(fib_mem.mem, DateStampDef, date_addr)
    t = os.path.getmtime(lock.sys_path)
    at = sys_to_ami_time(t)
    date.w_s('ds_Days', at.tday)
    date.w_s('ds_Minute', at.tmin)
    date.w_s('ds_Tick', at.tick)
    
    