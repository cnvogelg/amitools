from MemoryLayout import MemoryLayout
from MemoryLib import MemoryLib
from AmigaResident import AmigaResident
from Trampoline import Trampoline
from CPU import *

from Log import log_lib
import logging

class LibManager(MemoryLayout):
  def __init__(self, addr, size):
    MemoryLayout.__init__(self, "lib_mgr", addr, size)
    self.lib_addr = addr
    self.libs = {}
    self.addr_map = {}
    self.native_libs = {}
    self.native_addr_map = {}
  
  def register_lib(self, lib_class):
    self.libs[lib_class.get_name()] = {
      'lib_class' : lib_class,
      'instance' : None
    }
    
  def unregister_lib(self, lib_class):
    del self.libs[lib_class.get_name()]
  
  def lib_log(self, func, text, level=logging.INFO):
    log_lib.log(level, "LibMgr: [%10s] %s", func, text)
  
  def _get_next_lib_addr(self, size):
    res = self.lib_addr
    s = (size + 0xffff) & ~0xffff 
    self.lib_addr += s
    return res
  
  # ----- common -----
  
  # return (lib_instance)
  def open_lib(self, name, ver, context):
    # open internal lib
    if self.libs.has_key(name):
      return self.open_internal_lib(name, ver, context)
    # try to open native lib
    instance = self.open_native_lib(name, ver, context)
    if instance == None:
      self.lib_log("open_lib","Library not found: %s" % (name))
      return None
    else:
      return instance

  # return instance or null
  def close_lib(self, addr, context):
    # is an internal lib?
    if self.addr_map.has_key(addr):
      return self.close_internal_lib(addr, context)
    # is a native lib?
    elif self.native_addr_map.has_key(addr):
      return self.close_native_lib(addr, context)
    else:
      self.lib_log("close_lib","No library found at address %06x" % (addr))
      return None

  # ----- native lib -----

  def open_native_lib(self, name, ver, context):
    # check name
    if name.find(':') == -1 and name.find('/') == -1:
      name = "libs:" + name
      
    # use path manager to find real path
    real_path = context.path_mgr.ami_to_sys_path(name)
    if real_path == None:
      self.lib_log("open_lib","Can't find sys path for '%s'" % name, level=logging.ERROR)
      return None
    
    # use seg_loader to load lib
    self.lib_log("open_lib","Trying to load native lib: %s -> %s" % (name, real_path))
    seg_list = context.seg_loader.load_seg(real_path)
    if seg_list == None:
      self.lib_log("open_lib","Can't load library file '%s'" % real_path, level=logging.ERROR)
      return None
    
    # check seg list for resident library struct
    ar = AmigaResident()
    res_list = ar.find_residents(seg_list[0], context.mem)
    if res_list == None or len(res_list) != 1:
      self.lib_log("open_lib","No single resident found!", level=logging.ERROR)
      return None
    
    # make sure its a library
    res = res_list[0]
    if res['type'] != AmigaResident.NT_LIBRARY:
      self.lib_log("open_lib","Resident is not a library!", level=logging.ERROR)
      return None
    
    # resident is ok
    lib_name = res['name']
    lib_id = res['id']
    lib_version = res['version']
    auto_init = res['auto_init']
    self.lib_log("open_lib", "found resident: name='%s' id='%s'" % (lib_name, lib_id))
    
    # read auto init infos
    if not ar.read_auto_init_data(res, context.mem):
      self.lib_log("open_lib","Error reading auto_init!", level=logging.ERROR)
      return None
    
    # get library base info
    vectors  = res['vectors']
    pos_size = res['dataSize']
    total_size = pos_size + len(vectors) * 6

    # now create a memory lib instance
    lib_addr = context.alloc.alloc_range(total_size)
    instance = MemoryLib(lib_name, lib_addr, len(vectors), pos_size)
    context.alloc.reg_range(lib_addr, instance)
    lib_base = instance.get_lib_base()
  
    # setup lib instance memory
    hex_vec = map(lambda x:"%06x" % x, res['vectors'])
    self.lib_log("open_lib", "setting up vectors=%s" % hex_vec, level=logging.DEBUG)
    instance.set_all_vectors(vectors)
    self.lib_log("open_lib", "setting up struct=%s and lib" % res['struct'], level=logging.DEBUG)
    ar.init_lib(res, instance, lib_base)
    self.lib_log("open_lib", "init_code=%06x dataSize=%06x" % (res['init_code_ptr'],res['dataSize']), level=logging.DEBUG)

    # do we need to call init code of lib?
    init_addr = res['init_code_ptr']
    if init_addr != 0:
      # now prepare to execute library init code
      # setup trampoline to call init routine of library
      # D0 = lib_base, A0 = seg_list, A6 = exec base
      exec_base = context.mem.read_mem(2,4)
      tr = Trampoline()
      tr.save_all()
      tr.set_dx_l(0, lib_base)
      tr.set_ax_l(0, seg_list[0].addr)
      tr.set_ax_l(6, exec_base)
      tr.jsr(init_addr)
      tr.restore_all()
      tr.rts()
      tr_size = tr.get_code_size()
      tr_mem = context.alloc.alloc_memory("tr_"+lib_name, tr_size)
      tr.write_code(tr_mem)
      self.lib_log("open_lib","trampoline: %s" % tr_mem)
    
      # place the trampoline code ptr on stack
      old_stack = context.cpu.r_reg(REG_A7)
      new_stack = old_stack - 4
      context.cpu.w_reg(REG_A7, new_stack)
      context.mem.write_mem(2,new_stack, tr_mem.addr)

    # register lib
    entry = {
      'name' : lib_name,
      'id' : lib_id,
      'version' : res['version'],
      'instance' : instance,
      'seg_list' : seg_list,
      'lib_base' : lib_base,
      'trampoline' : tr_mem
    }
    self.native_libs[entry['name']] = entry
    self.native_addr_map[lib_base] = entry

    # return MemoryLib instance
    self.lib_log("open_lib", "Openend native '%s' V%d: base=%06x mem=%s" % (lib_name, lib_version, lib_base, instance))
    return instance

  def close_native_lib(self, addr, context):
    # get entry for lib
    entry = self.native_addr_map[addr]
    del self.native_addr_map[addr]
    del self.native_libs[entry['name']]

    # lib param
    name = entry['name']
    version = entry['version']
    lib_base = entry['lib_base']
    instance = entry['instance']
    self.lib_log("close_lib","Closed native '%s' V%d: base=%06x mem=%s]" % (name, version, lib_base, instance))

    # unreg and remove alloc
    context.alloc.unreg_range(instance.addr)
    context.alloc.free_range(instance.addr, instance.size)
    context.alloc.free_memory(entry['trampoline'])

    return instance

  # ----- internal lib -----

  def open_internal_lib(self, name, ver, context):
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
      pos_size = lib_class.get_pos_size()
      num_vecs = lib_class.get_num_vectors()
      struct   = lib_class.get_struct()
      lib_addr = self._get_next_lib_addr(lib_size)
      # create lib instance
      instance = MemoryLib(name, lib_addr, num_vecs, pos_size, struct=struct, lib=lib_class, context=context)
      self.add_range(instance)
      entry['instance'] = instance
      # store base_addr
      lib_base = instance.get_lib_base()
      entry['lib_base'] = lib_base
      self.addr_map[lib_base] = entry
      # call open on lib
      lib_class.open(instance,context)
      entry['ref_cnt'] = 0
          
    entry['ref_cnt'] += 1
    self.lib_log("open_lib","Opened %s V%d ref_count=%d base=%06x" % (name, lib_ver, entry['ref_cnt'], entry['lib_base']))
    return instance

  def close_internal_lib(self, addr, context):
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
      
