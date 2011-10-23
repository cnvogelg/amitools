import sys
from Log import log_file

class AmiFile:
  def __init__(self, obj, name):
    self.obj = obj
    self.name = name
    self.addr = 0
    self.b_addr = 0
    
  def __str__(self):
    return "[FH:'%s'@%06x=B@%06x]" % (self.name, self.addr, self.b_addr)

class FileManager:
  def __init__(self, path_mgr, base_addr):
    self.path_mgr = path_mgr
    self.base_addr = base_addr
    self.cur_addr = base_addr
    log_file.info("init manager: base=%06x" % self.base_addr)
    self.files_by_b_addr = {}
    # setup std input/output
    self.std_input = AmiFile(sys.stdin,'<STDIN>')
    self.std_output = AmiFile(sys.stdout,'<STDOUT>')
    self.nil = AmiFile(None,"NIL:")
    self._register_file(self.std_input)
    self._register_file(self.std_output)
    self._register_file(self.nil)
    
  def _register_file(self, fh):
    addr = self.cur_addr
    self.cur_addr += 4
    fh.addr = addr
    fh.b_addr = addr >> 2
    self.files_by_b_addr[fh.b_addr] = fh
    log_file.info("registered: %s" % fh)
  
  def _unregister_file(self,fh):
    check = self.files[fh.addr]
    if check != fh:
      raise ValueError("Invalid File to unregister: %s" % fh)
    del self.files_by_b_addr[fh.b_addr]
    fh.addr = 0
    fh.b_addr = 0
    log_file_info("unregistered: %s"% fh)
    
  def get_input(self):
    return self.std_input
  
  def get_output(self):
    return self.std_output
    
  def get_nil(self):
    return self.nil
    
  def open(self, name, f_mode):
    fobj = open(name, f_mode)
    fh = AmiFile(fobj, name)
    self._register_file(fh)
    return fh
  
  def close(self, fh):
    fh.obj.close()
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
