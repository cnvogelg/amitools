from LabelLib import LabelLib
from AmigaResident import AmigaResident
from AmigaLibrary import AmigaLibrary
from Trampoline import Trampoline
from CPU import *
from lib.lexec.ExecStruct import LibraryDef
from Exceptions import *
from Log import log_libmgr, log_lib
import amitools.fd.FDFormat as FDFormat
import logging
import time
import os

class LibManager():
  
  op_jmp = 0x4ef9
  
  def __init__(self, label_mgr, data_dir, benchmark=False, auto_create=True):
    self.data_dir = data_dir
    self.label_mgr = label_mgr
    
    # auto create missing libs
    self.auto_create = auto_create
    # map of registered libs: name -> AmigaLibrary
    self.reg_libs = {}
    # map of opened libs: base_addr -> AmigaLibrary
    self.open_libs_addr = {}
    self.open_libs_name = {}
    
    # use fast call? -> if lib logging level is ERROR or OFF
    self.log_call = log_lib.isEnabledFor(logging.WARN)
    self.benchmark = benchmark

    # libs will accumulate this if benchmarking is enabled
    self.bench_total = 0.0
  
  def register_int_lib(self, lib):
    """register an own library class"""
    self.reg_libs[lib.get_name()] = lib
    # init lib class instance
    lib.log_call = self.log_call
    lib.benchmark = self.benchmark
    lib.lib_mgr = self
    
  def unregister_int_lib(self, lib):
    """unregister your own library class"""
    del self.reg_libs[lib.get_name()]
  
  def lib_log(self, func, text, level=logging.INFO):
    """helper to create lib log messages"""
    log_libmgr.log(level, "[%10s] %s", func, text)
  
  # ----- common -----
  
  def open_lib(self, name, ver, ctx):
    """open a new library in memory
       return new AmigaLibrary instance that is setup or None if lib was not found
       
       Note: may prepare a trampoline to finish operation!
    """
    # sanitize lib name
    sane_name = self._get_sane_lib_name(name)
    
    # is lib already opened?
    if sane_name in self.open_libs_name:
      self.lib_log("open_lib","opening already open lib: %s" % sane_name)
      lib = self.open_libs_name[sane_name]
      if lib.is_native:
        # call Open()
        tr = Trampoline(ctx,"open_lib[%s]" % sane_name)
        self._open_native_lib(lib, ctx, tr)
        tr.final_rts()
        tr.done()
      else:
        # handle usage count
        lib.inc_usage()

    # lib has to be openend
    else:
      # otherwise try to find a lib instance in registered libs
      if sane_name in self.reg_libs:
        self.lib_log("open_lib","opening registered lib: %s" % sane_name)
        lib = self.reg_libs[sane_name]
      # auto create lib?
      elif self.auto_create:
        self.lib_log("open_lib","auto create lib: %s" % sane_name)
        lib = AmigaLibrary(sane_name, 0, LibraryDef)
        lib.is_auto_created = True
      # no chance to open lib
      else:
        self.lib_log("open_lib","opening failed: %s" % sane_name, level=logging.ERROR)
        return None

      # try to load an fd file for this lib
      lib.fd = self._load_fd(sane_name)

      # now check if the library has a native counterpart
      # if yes then create memory layout with it
      load_name = self._get_load_lib_name(name)
      if ctx.seg_loader.can_load_seg(load_name):
        # setup trampoline
        tr = Trampoline(ctx,"create_lib[%s]" % sane_name)
        self._create_native_lib(lib, load_name, ctx, tr)
        self._open_native_lib(lib, ctx, tr)
        tr.final_rts()
        tr.done()
      else:
        # own memory lib
        self._create_own_lib(lib, ctx)
        self._register_open_lib(lib)
        lib.inc_usage()
      
    return lib

  # return instance or null
  def close_lib(self, addr, ctx):
    # get lib object
    if addr not in self.open_libs_addr:
      self.lib_log("close_lib","No library found at address %06x" % (addr))
      return None
    lib = self.open_libs_addr[addr]
    
    # native lib handling
    if lib.is_native:
      tr = Trampoline(ctx,"close_lib[%s]" % lib.name)
      self._close_native_lib(lib, ctx, tr)
      if lib.ref_cnt == 0:
        self._free_native_lib(lib, ctx, tr)
      elif lib.ref_cnt < 0:
        raise VamosInternalError("CloseLib: invalid ref count?!")      
      tr.final_rts()
      tr.done()
      
    # own lib handling
    else:
      # decrement usage
      lib.dec_usage()
      # not used any more
      if lib.ref_cnt == 0:
        # finally close lib
        self._unregister_open_lib(lib)
        self._free_own_lib(lib, ctx)
      elif lib.ref_cnt < 0:
        raise VamosInternalError("CloseLib: invalid ref count?!")

    return lib

  # ----- post-open setup -----
  
  def _register_open_lib(self, lib):
    # now register lib
    self.open_libs_addr[lib.addr_base] = lib
    # own base per open?
    if lib.addr_base != lib.addr_base_open:
      self.open_libs_addr[lib.addr_base_open] = lib
    self.open_libs_name[lib.name] = lib
  
  def _unregister_open_lib(self, lib):
    # unregister lib
    del self.open_libs_addr[lib.addr_base]
    # own base per open?
    if lib.addr_base != lib.addr_base_open:
      del self.open_libs_addr[lib.addr_base_open]
    del self.open_libs_name[lib.name]

  # ----- open/close native lib -----

  def _open_native_lib(self, lib, ctx, tr):
    """call Open() on native lib"""  
    open_addr = lib.vectors[0]
    lib_base = lib.addr_base
    self.lib_log("open_lib","trampoline: open @%06x (lib_base/a6=%06x)" % (open_addr,lib_base), level=logging.DEBUG)
    tr.save_all()
    tr.set_ax_l(6, lib_base)
    tr.jsr(open_addr)
    # fetch the result (the lib base might have been altered)
    def trap_open_native_lib():
      self._open_native_lib_part2(lib, ctx)
    tr.trap(trap_open_native_lib)
    tr.restore_all()

    # update ref count
    lib.ref_cnt += 1
    return lib
    
  def _open_native_lib_part2(self, lib, ctx):
    lib.addr_base_open = ctx.cpu.r_reg(REG_D0)
    self.lib_log("open_lib", "done opening native lib: %s" % lib, level=logging.DEBUG)
    self._register_open_lib(lib)
    
  def _close_native_lib(self, lib, ctx, tr):
    """call Close() on native lib"""
    # add Close() call to trampoline
    close_addr = lib.vectors[1]
    lib_base = lib.addr_base_open
    self.lib_log("close_lib","trampoline: close @%06x (lib_base/a6=%06x)" % (close_addr,lib_base), level=logging.DEBUG)
    tr.save_all()
    tr.set_ax_l(6, lib_base)
    tr.jsr(close_addr)
    # fetch the result of the close call
    def trap_close_native_lib():
      self._close_native_lib_part2(lib, ctx)
    tr.trap(trap_close_native_lib)
    tr.restore_all()
    
    # update ref count
    lib.ref_cnt -= 1
    return lib
  
  def _close_native_lib_part2(self, lib, ctx):
    result = ctx.cpu.r_reg(REG_D0)
    self._unregister_open_lib(lib)
    self.lib_log("close_lib", "done closing native lib: %s seg_list=%06x" % (lib, result), level=logging.DEBUG)
  
  # ----- create/free native lib -----
  
  def _create_native_lib(self, lib, load_name, ctx, tr):
    """load native lib from binary file and allocate memory"""
    
    # use seg_loader to load lib
    self.lib_log("load_lib","loading native lib: %s" % load_name)
    lib.seg_list = ctx.seg_loader.load_seg(load_name)
    if lib.seg_list == None:
      self.lib_log("load_lib","Can't load library file '%s'" % load_name, level=logging.ERROR)
      return None
    
    # check seg list for resident library struct
    seg0 = lib.seg_list.segments[0]
    ar = AmigaResident(seg0.addr, seg0.size, ctx.mem)
    start = time.clock()
    res_list = ar.find_residents()
    end = time.clock()
    delta = end - start;
    if res_list == None or len(res_list) != 1:
      self.lib_log("load_lib","No single resident found!", level=logging.ERROR)
      return None
    
    # make sure its a library
    res = res_list[0]
    if res['type'] != AmigaResident.NT_LIBRARY:
      self.lib_log("load_lib","Resident is not a library!", level=logging.ERROR)
      return None
    
    # resident is ok
    lib_name = res['name']
    lib_id = res['id']
    lib.mem_version = res['version']
    auto_init = res['auto_init']
    self.lib_log("load_lib", "found resident: name='%s' id='%s' in %.4fs" % (lib_name, lib_id, delta), level=logging.DEBUG)
    
    # read auto init infos
    if not ar.read_auto_init_data(res, ctx.mem):
      self.lib_log("load_lib","Error reading auto_init!", level=logging.ERROR)
      return None
    
    # get library base info
    lib.vectors = res['vectors']
    lib.mem_pos_size = res['dataSize']
    lib.mem_neg_size = len(lib.vectors) * 6
    lib.is_native = True
    
    # allocate lib base
    lib.alloc_lib_base(ctx)
    self.lib_log("load_lib","allocated %s" % lib)
  
    # setup lib instance memory
    hex_vec = map(lambda x:"%06x" % x, res['vectors'])
    self.lib_log("load_lib", "setting up vectors=%s" % hex_vec, level=logging.DEBUG)
    self._set_all_vectors(ctx.mem, lib.addr_base, lib.vectors)
    self.lib_log("load_lib", "setting up struct=%s and lib" % res['struct'], level=logging.DEBUG)
    ar.init_lib(res, lib, lib.addr_base)
    self.lib_log("load_lib", "init_code=%06x dataSize=%06x" % (res['init_code_ptr'],res['dataSize']), level=logging.DEBUG)

    # do we need to call init code of lib?
    init_addr = res['init_code_ptr']
    if init_addr != 0:
      # now prepare to execute library init code
      # setup trampoline to call init routine of library
      # D0 = lib_base, A0 = seg_list, A6 = exec base
      exec_base = ctx.mem.read_mem(2,4)
      tr.save_all()
      tr.set_dx_l(0, lib.addr_base)
      tr.set_ax_l(0, lib.seg_list.b_addr) # baddr!
      tr.set_ax_l(6, exec_base)
      tr.jsr(init_addr)
      tr.restore_all()
      def trap_create_native_lib():
        self._create_native_lib_part2(lib, ctx)
      tr.trap(trap_create_native_lib)
      self.lib_log("load_lib", "trampoline: init @%06x (lib_base/d0=%06x seg_list/a0=%06x exec_base/a6=%06x)" % \
        (init_addr, lib.addr_base, seg0.addr, exec_base), level=logging.DEBUG)
    else:
      self._create_native_lib_part2(lib, ctx)
      
    return lib

  def _create_native_lib_part2(self, lib, ctx):
    self.lib_log("load_lib", "done loading native lib: %s" % lib)

  def _set_all_vectors(self, mem, base_addr, vectors):
    """set all library vectors to valid addresses"""
    addr = base_addr - 6
    for v in vectors:
      mem.write_mem(1,addr,self.op_jmp)
      mem.write_mem(2,addr+2,v)
      addr -= 6

  def _free_native_lib(self, lib, ctx, tr):
    # get expunge func
    expunge_addr = lib.vectors[2]
    exec_base = ctx.mem.read_mem(2,4)
    lib_base = lib.addr_base
    if expunge_addr != 0:
      # setup trampoline to call expunge and then part2 of unload
      tr.save_all()
      tr.set_ax_l(6, lib_base)
      tr.jsr(expunge_addr)
      tr.restore_all()
      # close lib via trampoline trap after expunge code was run
      def trap_free_native_lib():
        self._free_native_lib_part2(lib, ctx, False)
      tr.trap(trap_free_native_lib)
      self.lib_log("free_lib","trampoline: expunge @%06x (lib_base/a6=%06x)" % (expunge_addr, lib_base), level=logging.DEBUG)
    else:
      self._free_native_lib_part2(lib, ctx, True)

  def _free_native_lib_part2(self, lib, ctx, do_free):
    result = ctx.cpu.r_reg(REG_D0)
    self.lib_log("free_lib","after expunge: seg_list=%06x" % (result), level=logging.DEBUG)    

    # lib finish
    lib.finish_lib(ctx)
    # free base
    lib.free_lib_base(ctx, do_free)

    # unload seg_list
    ctx.seg_loader.unload_seg(lib.seg_list)
    lib.seg_list = None

    self.lib_log("free_lib","done freeing native lib: %s" % lib)

  # ----- own memory lib creation without loading a binary lib first -----

  def _create_own_lib(self, lib, ctx):
    """create an own library structure in memory for the given lib"""          
    self.lib_log("create_lib","creating own mem lib for %s" % lib.name)
    # we need a FD description for the library otherwise we don't know neg size
    # (TBD: later on we might force a (neg) size)
    if lib.fd == None:
      raise VamosConfigError("Missing FD file '%s' for internal lib!" % lib.name)
    # setup library size (pos, neg) from fd file and class instance
    lib.calc_neg_size_from_fd()
    # use proposed version
    lib.mem_version = lib.version
    # take calc sizes from fd and struct for lib memory layout
    lib.use_sizes()
    # allocate memory for library base
    lib.alloc_lib_base(ctx)
    self.lib_log("create_lib","created %s" % lib)
    
    # fill in some values into lib structure (version, pos size, neg size, ...)
    lib.fill_lib_struct()
    # create an empty jump table
    lib.create_empty_jump_table(ctx)
    # patch in functions
    res = lib.trap_class_entries(ctx)
    if res != None:
      self.lib_log("create_lib","patched in %d python functions, created %d dummy functions" % res)

    # finally setup lib
    lib.setup_lib(ctx)
    self.lib_log("create_lib","library %s is setup" % lib.name)

  def _free_own_lib(self, lib, ctx):
    """free memory foot print of own allocated library"""
    self.lib_log("free_lib","own mem library %s is finishing" % lib.name)

    # first call finish lib
    lib.finish_lib(ctx)
    # free memory allocation
    lib.free_lib_base(ctx)
    
    self.lib_log("free_lib","own mem library %s is freed" % lib.name)
      
  # ----- Helpers -----
  
  def _load_fd(self, lib_name):
    """try to load a fd file for a library from vamos data dir"""
    fd_name = lib_name.replace(".library","_lib.fd")
    pos = fd_name.rfind(":")
    if pos != -1:
      fd_name = fd_name[pos+1:]
    fd_file = os.path.join(self.data_dir,"fd",fd_name)
    # try to load fd file if it exists
    if os.path.exists(fd_file):
      try:
        begin = time.clock()
        fd = FDFormat.read_fd(fd_file)
        end = time.clock()
        delta = end - begin
        self.lib_log("load_fd","loaded fd file '%s' in %fs: base='%s' #funcs=%d" % (fd_file, delta, fd.get_base_name(), len(fd.get_funcs())))
        return fd
      except IOError as e:
        self.lib_log("load_fd","Failed reading fd file '%s'" % fd_file, level=logging.ERROR)
    else:
      self.lib_log("load_fd","no fd file found for library '%s'" % fd_file)
    return None
    
  def _get_sane_lib_name(self, name):
    """strip all path components"""
    result = name
    pos = result.rfind('/')
    if pos != -1:
      result = result[pos+1:]
    pos = result.rfind(':')
    if pos != -1:
      result = result[pos+1:]
    return result.lower()

  def _get_load_lib_name(self, name):
    # fix name
    if name.find(':') == -1 and name.find('/') == -1:
      name = "libs:" + name
    return name
