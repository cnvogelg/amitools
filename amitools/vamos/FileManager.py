import sys
import os.path
import logging

from Log import log_file
from LabelRange import LabelRange
from structure.DosStruct import FileHandleDef
from lib.dos.Error import *

class AmiFile:
  def __init__(self, obj, ami_path, sys_path, need_close=True):
    self.obj = obj
    self.name = os.path.basename(sys_path)
    self.ami_path = ami_path
    self.sys_path = sys_path
    self.addr = 0
    self.b_addr = 0
    self.need_close = need_close
    
  def __str__(self):
    return "[FH:'%s'(ami='%s',sys='%s',nc=%s)@%06x=B@%06x]" % (self.name, self.ami_path, self.sys_path, self.need_close, self.addr, self.b_addr)

  def close(self):
    if self.need_close:
      self.obj.close()

class FileManager(LabelRange):
  def __init__(self, path_mgr, base_addr, size):
    self.path_mgr = path_mgr
    self.base_addr = base_addr
    self.cur_addr = base_addr
    log_file.info("init manager: base=%06x" % self.base_addr)
    self.files_by_b_addr = {}
    LabelRange.__init__(self, "files", base_addr, size)
    self.fh_def  = FileHandleDef
    self.fh_size = FileHandleDef.get_size()
    self.fh_size = (self.fh_size + 3) & ~3

    # setup std input/output
    self.std_input = AmiFile(sys.stdin,'<STDIN>','',need_close=False)
    self.std_output = AmiFile(sys.stdout,'<STDOUT>','',need_close=False)
    self._register_file(self.std_input)
    self._register_file(self.std_output)
  
  def set_fs_handler_port(self, addr):
    self.fs_handler_port = addr
  
  def _register_file(self, fh):
    addr = self.cur_addr
    self.cur_addr += self.fh_size
    fh.addr = addr
    fh.b_addr = addr >> 2
    self.files_by_b_addr[fh.b_addr] = fh
    log_file.info("registered: %s" % fh)
  
  def _unregister_file(self,fh):
    check = self.files_by_b_addr[fh.b_addr]
    if check != fh:
      raise ValueError("Invalid File to unregister: %s" % fh)
    del self.files_by_b_addr[fh.b_addr]
    log_file.info("unregistered: %s"% fh)
    fh.addr = 0
    fh.b_addr = 0
  
  # directly read from file handle structure
  def r32_fh(self, addr):
    # find out associated file handle
    rel = int((addr - self.addr) / self.fh_size)
    fh_addr = self.addr + rel * self.fh_size
    b_addr = fh_addr >> 2
    fh = self.get_by_b_addr(b_addr)
    if fh != None:
      # get addon text
      delta = addr - fh_addr
      name,off,val_type_name = self.fh_def.get_name_for_offset(delta, 2)
      type_name = self.fh_def.get_type_name()
      addon="%s+%d = %s(%s)+%d  %s" % (type_name, delta, name, val_type_name, off, fh)

      # inject some special values to allow PutMsg handler access
      val = 0
      if name == 'fh_Args':
        # identifier for File -> use FH itself
        val = b_addr
      elif name == 'fh_Type':
        # PutMsg port
        val = self.fs_handler_port
      
      self.trace_mem_int('R', 2, addr, val, text="FILE", level=logging.INFO, addon=addon)
      return val
    else:
      self.trace_mem_int('R', 2, addr, val, text="FILE", level=logging.WARN)
      return 0
  
  def get_input(self):
    return self.std_input
  
  def get_output(self):
    return self.std_output
    
  def open(self, ami_path, f_mode):
    try:
      # special names
      uname = ami_path.upper()
      if uname == 'NIL:':
        sys_name = "/dev/null" 
        fobj = open(sys_name, f_mode)
        fh = AmiFile(fobj, ami_name, sys_name)
      elif uname in ('*','CONSOLE:'):
        sys_name = ''
        fh = AmiFile(sys.stdout,'*','',need_close=False)
      else:
        ami_path = self.path_mgr.ami_abs_path(ami_path)
        sys_path = self.path_mgr.ami_to_sys_path(ami_path)
        if sys_path == None:
          log_file.info("file not found: '%s' -> '%s'" % (ami_path, sys_path))
          return None
        fobj = open(sys_path, f_mode)
        fh = AmiFile(fobj, ami_path, sys_path)
    
      self._register_file(fh)
      return fh
    except IOError:
      log_file.info("error opening: '%s' -> '%s'" % (ami_path, sys_path))
      return None
  
  def close(self, fh):
    fh.close()
    self._unregister_file(fh)
  
  def get_by_b_addr(self, b_addr):
    if self.files_by_b_addr.has_key(b_addr):
      return self.files_by_b_addr[b_addr]
    else:
      addr = b_addr << 2
      raise ValueError("Invalid File Handle at b@%06x = %06x" % (b_addr, addr))

  def write(self, fh, data):
    fh.obj.write(data)
    return len(data)

  def read(self, fh, len):
    d = fh.obj.read(len)
    return d

  def tell(self, fh):
    return fh.obj.tell()
  
  def seek(self, fh, pos, whence):
    fh.obj.seek(pos, whence)
    
  def delete(self, ami_path):
    ami_path = self.path_mgr.ami_abs_path(ami_path)
    sys_path = self.path_mgr.ami_to_sys_path(ami_path)
    if sys_path == None or not os.path.exists(sys_path):
      log_file.info("file to delete not found: '%s'" % (ami_path))
      return ERROR_OBJECT_NOT_FOUND
    try:
      os.remove(sys_path)
      return 0
    except OSError as e:
      log_file.info("can't delete file: '%s' -> %s" % (ami_path, e))
      return ERROR_OBJECT_IN_USE

  def rename(self, old_ami_path, new_ami_path):
    old_ami_path = self.path_mgr.ami_abs_path(old_ami_path)
    old_sys_path = self.path_mgr.ami_to_sys_path(old_ami_path)
    new_ami_path = self.path_mgr.ami_abs_path(new_ami_path)
    new_sys_path = self.path_mgr.ami_to_sys_path(new_ami_path)
    if old_sys_path == None or not os.path.exists(old_sys_path):
      log_file.info("old file to rename not found: '%s'" % old_ami_path)
      return ERROR_OBJECT_NOT_FOUND
    if new_sys_path == None:
      log_file.info("new file to rename not found: '%s'" % new_ami_path)
      return ERROR_OBJECT_NOT_FOUND
    try:
      os.rename(old_sys_path, new_sys_path)
      return 0
    except OSError as e:
      log_file.info("can't rename file: '%s','%s' -> %s" % (old_ami_path, new_amipath, e))
      return ERROR_OBJECT_IN_USE
    