# scan a set of file

import os
import StringIO

class FileScanner:
  
  def __init__(self, handler, use_adf = False):
    self.handler = handler
    if use_adf:
      import ADFScanner
      self.adf_scanner = ADFScanner.ADFScanner(lambda a,b,c: self.handle_adf_file(a,b,c))
    else:
      self.adf_scanner = None
  
  def call_handler(self, path, fobj):
    return self.handler(path, fobj)

  def handle_adf_file(self, img_path, file_path, data):
    vpath = img_path + ":" + file_path
    fobj = StringIO.StringIO(data)
    return self.call_handler(vpath, fobj)

  def handle_adf(self, path):
    if self.adf_scanner != None:
      return self.adf_scanner.scan_adf(path)
    else:
      return True

  def handle_file(self, path):
    if path.lower().endswith(".adf"):
        return self.handle_adf(path)
    with open(path) as fobj:
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