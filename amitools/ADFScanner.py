"""Scan an ADF image an visit all files"""

import subprocess

class ADFScanner:

  def __init__(self, unadf_exe, handler, stop_on_error=True):
    self.handler = handler
    self.unadf_exe = unadf_exe
    self.stop_on_error = stop_on_error

  def scan_adf(self, file_name):
    # call "lha l file" to get file list
    cmd = [ self.unadf_exe, '-lr', file_name]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    com = p.communicate()
    output = com[0]
    error = com[1]
    if p.returncode != 0:
      # no DOS disk? -> ignore it
      if error.find("<adfReadRootBlock : id not found>") != -1:
        return True
      elif self.stop_on_error:
        print error
        return False
      else:
        return True

     # process archive list
    lines = output.splitlines()
    file_list = []
    for entry in lines[3:]:
      entry_name = entry[31:]
      if not entry_name.endswith('/'):
        file_list.append(entry_name)

     # now extract the files 
    for entry_name in file_list:
       # call "lha p file.lha entry" to get a file 
       cmd = [self.unadf_exe, '-p', file_name, entry_name]
       p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
       com = p.communicate()
       data = com[0]
       error = com[1]
       if p.returncode != 0:
         print error
         return False
       if len(output) > 0:
         ok = self.handler(file_name, entry_name, data)
         if not ok:
           return False
    return True