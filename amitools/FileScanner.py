# scan a set of file

import os
import StringIO
import LHAScanner
import ADFScanner

class FileScanner:
  
  def __init__(self, handler, use_adf = None, use_lha = None, stop_on_error = True):
    self.handler = handler
    if use_adf:
      self.adf_scanner = ADFScanner.ADFScanner(use_adf, lambda a,b,c: self.handle_ext_file(a,b,c), stop_on_error=stop_on_error)
    else:
      self.adf_scanner = None
    if use_lha:
      self.lha_scanner = LHAScanner.LHAScanner(use_lha, lambda a,b,c: self.handle_ext_file(a,b,c))
    else:
      self.lha_scanner = None
  
  def call_handler(self, path, fobj):
    return self.handler(path, fobj)

  def handle_ext_file(self, img_path, file_path, data):
    vpath = img_path + ":" + file_path
    fobj = StringIO.StringIO(data)
    return self.call_handler(vpath, fobj)

  def handle_adf(self, path):
    if self.adf_scanner != None:
      return self.adf_scanner.scan_adf(path)
    else:
      return True

  def handle_lha(self, path):
    if self.lha_scanner != None:
      return self.lha_scanner.scan_lha(path)
    else:
      return True

  def handle_file(self, path):
    lpath = path.lower()
    if lpath.endswith(".adf"):
      return self.handle_adf(path)
    elif lpath.endswith(".lha"):
      return self.handle_lha(path)
    else:
      with open(path, "rb") as fobj:
        return self.call_handler(path, fobj)

  def handle_dir(self, path):
    for root, dirs, files in os.walk(path):
      for name in files:
        if not self.handle_file(os.path.join(root,name)):
          return False
      for name in dirs:
        if not self.handle_dir(os.path.join(root,name)):
          return False
    return True

  def handle_path(self, path):
    if os.path.isdir(path):
      return self.handle_dir(path)
    elif os.path.isfile(path):
      return self.handle_file(path)
    else:
      return True