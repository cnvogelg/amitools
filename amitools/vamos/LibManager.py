from MemoryLayout import MemoryLayout
from MemoryLib import MemoryLib

from Log import log_lib
import logging

class LibManager(MemoryLayout):
  def __init__(self, addr, size):
    MemoryLayout.__init__(self, "lib_mgr", addr, size)
    self.lib_addr = addr
    self.libs = {}
    self.addr_map = {}
  
  def register_lib(self, lib_class):
    self.libs[lib_class.get_name()] = {
      'lib_class' : lib_class,
      'instance' : None,
      'ref_count' : 0
    }
    
  def unregister_lib(self, lib_class):
    del self.libs[lib_class.get_name()]
  
  def _get_lib_addr(self, size):
    addr = self.lib_addr
    self.lib_addr += size
    return addr
  
  def lib_log(self, func, text, level=logging.INFO):
    log_lib.log(level, "LibMgr: [%10s] %s", func, text)
  
  # return (lib_instance)
  def open_lib(self, name, ver, context):
    # lib not found
    if not self.libs.has_key(name):
      self.lib_log("open_lib","Library not found: %s" % (name))
      return None
    
    # get lib entry
    entry = self.libs[name]
    lib_class = entry['lib_class']
    instance = entry['instance']
    entry['name'] = name
    entry['version'] = ver # requested version
    lib_ver = lib_class.get_version()

    # version correct?
    if ver != 0 and lib_ver < ver:
      self.lib_log("open_lib","Invalid library version: %s has %d, expected %d" % (name, lib_ver, ver))
      return None

    # create an instance
    if instance == None:
      # get memory range for lib
      lib_size = lib_class.get_total_size()      
      addr = self._get_lib_addr(lib_size)
      # create lib instance
      instance = MemoryLib(addr, lib_class, context)
      self.add_range(instance)
      entry['instance'] = instance
      # store base_addr
      base_addr = instance.get_base_addr()
      entry['base_addr'] = base_addr
      self.addr_map[base_addr] = entry
      # call open on lib
      lib_class.open(instance,context)
      entry['ref_cnt'] = 0
          
    entry['ref_cnt'] += 1
    self.lib_log("open_lib","Opened %s V%d ref_count=%d base=%06x" % (name, lib_ver, entry['ref_count'], entry['base_addr']))
    return instance

  # return instance or null
  def close_lib(self, addr, context):
    # find entry by addr
    if not self.addr_map.has_key(addr):
      self.lib_log("close_lib","No library found at address %06x" % (addr))
      return None
    entry = self.addr_map[addr]
    instance = entry['instance']
    lib_class = entry['lib_class']
    ver = lib_class.get_version();
    name = entry['name']
    ver = entry['version']
      
    # decrement ref_count
    ref_cnt = entry['ref_cnt']
    if ref_cnt < 1:
      self.lib_log("close_lib","Invalid ref_count ?!")
      return None
    elif ref_cnt > 1:
      ref_cnt -= 1;
      entry['ref_cnt'] = ref_cnt
      self.lib_log("close_lib","Closed %s V%d ref_count=%d]" % (name, ver, ref_cnt))
      return instance
    else:
      # remove lib instance
      entry['instance'] = None
      entry['ref_cnt'] = 0
      lib_class.close(instance,context)
      self.remove_range(instance)
      self.lib_log("close_lib","Closed %s V%d ref_count=0" % (name, ver))
      return instance
      
