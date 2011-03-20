"""Scan LHA archives and visit all files"""

import subprocess

class LHAScanner:

  def __init__(self, lha_exe, handler):
    self.handler = handler
    self.lha_exe = lha_exe

  def scan_lha(self, file_name):
    # call "lha l file" to get file list
    p = subprocess.Popen([self.lha_exe, 'l',file_name], stdout=subprocess.PIPE)
    output = p.communicate()[0]
    if p.returncode != 0:
      return False
  
    # process archive list
    lines = output.splitlines()
    file_list = []
    for entry in lines[2:-2]:
      entry_name = entry[51:]
      file_list.append(entry_name)
      
    # now extract the files 
    for entry_name in file_list:
      # call "lha p file.lha entry" to get a file 
      cmd = [self.lha_exe, 'pq',file_name,entry_name]
      p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
      data = p.communicate()[0]
      if p.returncode != 0:
        return False
      if len(output) > 0:
        ok = self.handler(file_name, entry_name, data)
        if not ok:
          return False

    return True