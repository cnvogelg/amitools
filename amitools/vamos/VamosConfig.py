import ConfigParser
import os
import os.path

from Log import log_main

class VamosConfig(ConfigParser.SafeConfigParser):
  def __init__(self, extra_file=None):
    ConfigParser.SafeConfigParser.__init__(self)
    self.files = []
    
    # prepend extra file
    if extra_file != None:
      self.files.append(extra_file)    
    # add config in current working dir
    self.files.append(os.path.join(os.getcwd(),".vamosrc"))
    # add config in home directory
    self.files.append(os.path.expanduser("~/.vamosrc"))
    
    # read configs
    self.found_files = self.read(self.files)
    if len(self.found_files) == 0:
      log_main.warn("no config file found: %s" % ",".join(self.files))
    else:
      log_main.info("read config file: %s" % ",".join(self.found_files))
