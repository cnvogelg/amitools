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
    self.handler(path, fobj)

  def handle_adf_file(self, img_path, file_path, data):
    vpath = img_path + ":" + file_path
    fobj = StringIO.StringIO(data)
    self.call_handler(vpath, fobj)

  def handle_adf(self, path):
    if self.adf_scanner != None:
      self.adf_scanner.scan_adf(path)

  def handle_file(self, path):
    if path.lower().endswith(".adf"):
        self.handle_adf(path)
        return
    with open(path) as fobj:
      self.call_handler(path, fobj)

  def handle_dir(self, path):
    for root, dirs, files in os.walk(path):
      for name in files:
        self.handle_file(os.path.join(root,name))
      for name in dirs:
        self.handle_dir(os.path.join(root,name))

  def handle_path(self, path):
    if os.path.isdir(path):
      self.handle_dir(path)
    elif os.path.isfile(path):
      self.handle_file(path)
  