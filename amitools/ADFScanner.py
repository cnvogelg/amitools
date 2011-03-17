"""Scan an ADF image an visit all files"""

from pyadf import Adf, AdfIOException

ST_DIR = 2
ST_FILE = -3

class ADFScanner:

  def __init__(self, handler):
    self.handler = handler

  def scan_dir(self, file_name, dir_path, adf):
    entries = adf.ls_dir(dir_path)
    for entry in entries:
      name = entry.fname
      if dir_path == "":
        path = name
      else:
        path = dir_path + "/" + name
      if entry.ftype == ST_DIR:
        return self.scan_dir(file_name, path, adf)
      elif entry.ftype == ST_FILE:
        try:
          data = adf.get_file(path)
          return self.handler(file_name, path, data)
        except AdfIOException, info:
          return False
      else:
        return True

  def scan_adf(self, file_name):
    adf = Adf(file_name, mode='r')
    return self.scan_dir(file_name, "", adf)
