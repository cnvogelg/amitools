from LabelLib import LabelLib
from AmigaResident import AmigaResident
from Trampoline import Trampoline
from CPU import *
from structure.ExecStruct import LibraryDef
from Exceptions import *
from Log import log_lib
from AccessStruct import AccessStruct
import logging

class LibEntry():
  def __init__(self, name, version, addr, num_vectors, pos_size, mem, label_mgr, struct=LibraryDef, lib_class=None):
    self.name = name
    self.version = version
    self.lib_class = lib_class
    self.struct = struct

    self.num_vectors = num_vectors
    self.pos_size = pos_size
    self.neg_size = num_vectors * 6
    self.size = self.pos_size + self.neg_size

    self.lib_begin = addr
    self.lib_base  = addr + self.neg_size
    self.lib_end   = self.lib_base + self.pos_size

    self.ref_cnt = 0
    self.lib_id = None
    
    self.access = AccessStruct(mem, label_mgr, struct, self.lib_base)
    self.label = None
    
    # native lib only
    self.trampoline = None
    self.seg_list = None

class LibManager():
  
  op_rts = 0x4e75
  op_jmp = 0x4ef9
  op_reset = 0x04e70
  
  def __init__(self, label_mgr):
    self.label_mgr = label_mgr
    self.int_lib_classes = {}
    self.int_libs = {}
    self.int_addr_map = {}
    self.native_libs = {}
    self.native_addr_map = {}
    self.lib_trap_table = []
  
  def register_int_lib(self, lib_class):
    self.int_lib_classes[lib_class.get_name()] = lib_class
    
  def unregister_int_lib(self, lib_class):
    del self.int_lib_classes[lib_class.get_name()]
  
  def lib_log(self, func, text, level=logging.INFO):
    log_lib.log(level, "LibMgr: [%10s] %s", func, text)
  
  # ----- common -----
  
  # return (lib_instance)
  def open_lib(self, name, ver, context):
    # open internal lib
    if self.int_lib_classes.has_key(name):
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
    if self.int_addr_map.has_key(addr):
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
      self.lib_log("open_lib","Can't load library file '%s' -> '%s'" % (name, real_path), level=logging.ERROR)
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
    lib_addr = context.alloc.alloc_mem(total_size)
    entry = LibEntry(lib_name, lib_version, lib_addr, len(vectors), pos_size, context.mem, self.label_mgr)
    lib_base = entry.lib_base

    # create a memory label
    label = LabelLib(lib_name, lib_addr, entry.size, lib_base, LibraryDef)
    entry.label = label
    self.label_mgr.add_label(label)
  
    # setup lib instance memory
    hex_vec = map(lambda x:"%06x" % x, res['vectors'])
    self.lib_log("open_lib", "setting up vectors=%s" % hex_vec, level=logging.DEBUG)
    self.set_all_vectors(context.mem, lib_base, vectors)
    self.lib_log("open_lib", "setting up struct=%s and lib" % res['struct'], level=logging.DEBUG)
    ar.init_lib(res, entry, lib_base)
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
      self.lib_log("open_lib","trampoline: %s" % tr_mem, level=logging.DEBUG)
    
      # place the trampoline code ptr on stack
      old_stack = context.cpu.r_reg(REG_A7)
      new_stack = old_stack - 4
      context.cpu.w_reg(REG_A7, new_stack)
      context.mem.write_mem(2,new_stack, tr_mem.addr)

    # store native components
    entry.trampoline = tr_mem
    entry.seg_list = seg_list

    # register lib
    self.native_libs[entry.name] = entry
    self.native_addr_map[lib_base] = entry

    # return MemoryLib instance
    self.lib_log("open_lib", "Openend native '%s' V%d: base=%06x label=%s" % (lib_name, lib_version, lib_base, label))
    return entry

  def close_native_lib(self, addr, context):
    # get entry for lib
    entry = self.native_addr_map[addr]
    del self.native_addr_map[addr]
    del self.native_libs[entry.name]

    # lib param
    name = entry.name
    version = entry.version
    lib_base = entry.lib_base
    label = entry.label
    self.lib_log("close_lib","Closed native '%s' V%d: base=%06x label=%s]" % (name, version, lib_base, label))

    # unreg and remove alloc
    self.label_mgr.remove_label(label)
    context.alloc.free_range(entry.lib_begin, entry.size)
    context.alloc.free_memory(entry.trampoline)

    return entry

  def set_all_vectors(self, mem, base_addr, vectors):
    """set all library vectors to valid addresses"""
    addr = base_addr - 6
    for v in vectors:
      mem.write_mem(1,addr,self.op_jmp)
      mem.write_mem(2,addr+2,v)
      addr -= 6

  # ----- internal lib -----

  def open_internal_lib(self, name, ver, context):
    # get lib_class
    lib_class = self.int_lib_classes[name]
    lib_ver = lib_class.get_version()
    
    # version correct?
    if ver != 0 and lib_ver < ver:
      raise VersionMismatchError(name, lib_ver, ver)
      
    # do we have a lib entry already?
    if not self.int_libs.has_key(name):
      # get memory range for lib
      lib_size = lib_class.get_total_size()     
      pos_size = lib_class.get_pos_size()
      num_vecs = lib_class.get_num_vectors()
      struct   = lib_class.get_struct()

      # allocate and create lib instance
      lib_addr = context.alloc.alloc_mem(lib_size)
      entry = LibEntry(name, ver, lib_addr, num_vecs, pos_size, context.mem, self.label_mgr, struct, lib_class)
      lib_base = entry.lib_base
      
      # create memory label
      label = LabelLib(name, lib_addr, lib_size, lib_base, struct)
      entry.label = label
      self.label_mgr.add_label(label)

      # store entry in address map, too
      self.int_addr_map[lib_base] = entry
      self.int_libs[name] = entry

      # setup traps in internal lib
      lib_id = len(self.lib_trap_table)
      self.lib_trap_table.append(entry)
      self.trap_all_vectors(context.mem, lib_base, num_vecs, lib_id)
      entry.lib_id = lib_id
      
      # call open on lib
      lib_class.open(entry, context)
    else:
      entry = self.int_libs[name]
          
    entry.ref_cnt += 1
    self.lib_log("open_lib","Opened %s V%d ref_count=%d base=%06x" % (name, lib_ver, entry.ref_cnt, entry.lib_base))
    return entry

  def close_internal_lib(self, addr, context):
    entry = self.int_addr_map[addr]
    name = entry.name
    ver = entry.version
    
    # decrement ref_count
    ref_cnt = entry.ref_cnt
    if ref_cnt < 1:
      raise VamosInternalError("CloseLib: invalid ref count?!")
    elif ref_cnt > 1:
      ref_cnt -= 1;
      entry.ref_cnt = ref_cnt
      self.lib_log("close_lib","Closed %s V%d ref_count=%d]" % (name, ver, ref_cnt))
      return entry
    else:
      # call lib to close
      lib_class = entry.lib_class
      lib_class.close(entry,context)
      # remove entry in trap table
      lib_id = entry.lib_id
      self.lib_trap_table[lib_id] = None
      # unregister label
      self.label_mgr.remove_label(entry.label)
      # free memory
      context.alloc.free_mem(entry.lib_begin, entry.size)
      self.lib_log("close_lib","Closed %s V%d ref_count=0" % (name, ver))
      return entry
      
  def call_internal_lib(self, addr, ctx):
    lib_id = ctx.mem.read_mem(1, addr+4)
    tab = self.lib_trap_table
    if lib_id >= len(tab):
      raise VamosInternalError("Invalid lib trap!")
    entry = tab[lib_id]
    base = entry.lib_base
    offset = base - addr
    num = offset / 6
    log_lib.debug("Call Lib: %06x lib_id=%d -> offset=%d %s" % (addr, lib_id, offset, entry.name))
    entry.lib_class.call_vector(num,entry,ctx)

  def trap_all_vectors(self, mem, base_addr, num_vectors, lib_id):
    """prepare the entry points for trapping. place RESET, RTS opcode and lib_id"""
    addr = base_addr - 6
    for i in xrange(num_vectors):
      mem.write_mem(1,addr,self.op_reset)
      mem.write_mem(1,addr+2,self.op_rts)
      mem.write_mem(1,addr+4,lib_id)
      addr -= 6

  