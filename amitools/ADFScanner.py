"""Scan an ADF image an visit all files"""

from pyadf import Adf, AdfIOException

ST_DIR = 2
ST_FILE = -3

def scan_dir(file_name, visit_func, dir_path, adf):
  entries = adf.ls_dir(dir_path)
  for entry in entries:
    name = entry.fname
    if dir_path == "":
      path = name
    else:
      path = dir_path + "/" + name
    if entry.ftype == ST_DIR:
      scan_dir(file_name, visit_func, path, adf)
    elif entry.ftype == ST_FILE:
      try:
        data = adf.get_file(path)
        visit_func(file_name, path, data)
      except AdfIOException, info:
        pass

def scan_adf(file_name, visit_func):
  adf = Adf(file_name, mode='r')
  scan_dir(file_name, visit_func, "", adf)