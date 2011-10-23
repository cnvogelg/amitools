import sys
import os.path
from Log import log_file

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

class FileManager:
  def __init__(self, path_mgr, base_addr):
    self.path_mgr = path_mgr
    self.base_addr = base_addr
    self.cur_addr = base_addr
    log_file.info("init manager: base=%06x" % self.base_addr)
    self.files_by_b_addr = {}
    # setup std input/output
    self.std_input = AmiFile(sys.stdin,'<STDIN>','',need_close=False)
    self.std_output = AmiFile(sys.stdout,'<STDOUT>','',need_close=False)
    self._register_file(self.std_input)
    self._register_file(self.std_output)
    
  def _register_file(self, fh):
    addr = self.cur_addr
    self.cur_addr += 4
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
    
  def get_input(self):
    return self.std_input
  
  def get_output(self):
    return self.std_output
    
  def open(self, ami_path, f_mode):
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
      sys_path = self.path_mgr.ami_to_sys_path(ami_path)
      if sys_path == None:
        log_file.info("file not found: '%s' -> '%s'" % (ami_path, sys_path))
        return None
      fobj = open(sys_path, f_mode)
      fh = AmiFile(fobj, ami_path, sys_path)
    
    self._register_file(fh)
    return fh
  
  def close(self, fh):
    fh.close()
    self._unregister_file(fh)
  
  def get_by_b_addr(self, b_addr):
    if self.files_by_b_addr.has_key(b_addr):
      return self.files_by_b_addr[b_addr]
    else:
      raise ValueError("Invalid File Handle at b@%06x" % b_addr)

  def write(self, fh, data):
    fh.obj.write(data)
    return len(data)

  def read(self, fh, len):
    d = fh.obj.read(len)
    return d
