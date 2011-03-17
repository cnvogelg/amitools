# scan a set of hunks

import os
import Hunk

class HunkScanner:
  
  def __init__(self, handler, use_adf = False, ignore_no_hunk = True):
    self.ignore_no_hunk = ignore_no_hunk
    self.handler = handler
    if use_adf:
      import ADFScanner
      self.adf_scanner = ADFScanner.ADFScanner(lambda a,b,c: self.handle_adf_file(a,b,c))
    else:
      self.adf_scanner = None
  
  def call_handler(self, path, hunk_file, return_code):
    if return_code == Hunk.RESULT_NO_HUNK_FILE and self.ignore_no_hunk:
      return
    self.handler(path, hunk_file, return_code)

  def handle_adf_file(self, img_path, file_path, data):
    vpath = img_path + ":" + file_path
    hf = Hunk.HunkFile()
    result = hf.read_mem(vpath, data)
    self.call_handler(vpath, hf, result)

  def handle_adf(self, path):
    if self.adf_scanner != None:
      self.adf_scanner.scan_adf(path)

  def handle_file(self, path):
    if path.lower().endswith(".adf"):
        self.handle_adf(path)
        return

    hf = Hunk.HunkFile()
    result = hf.read_file(path)
    self.call_handler(path, hf, result)

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
  