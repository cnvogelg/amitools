from label.LabelLib import LabelLib
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

  def __init__(self, label_mgr, cfg):
    self.label_mgr = label_mgr
    self.cfg = cfg
    self.data_dir = cfg.data_dir

    # map of registered libs: name -> AmigaLibrary
    self.vamos_libs = {}
    # map of opened libs: base_addr -> AmigaLibrary
    self.open_libs_addr = {}
    self.open_libs_name = {}

    # use fast call? -> if lib logging level is ERROR or OFF
    self.log_call = log_lib.isEnabledFor(logging.INFO)
    self.log_dummy_call = log_lib.isEnabledFor(logging.WARN)
    self.benchmark = cfg.benchmark

    # libs will accumulate this if benchmarking is enabled
    self.bench_total = 0.0

    # --- config for auto lib ---
    # black and white list for auto creation of libs
    # (use sane or normal name)
    #self.black_list = []
    #self.white_list = ['icon.library']
    self.auto_create = False

  def register_vamos_lib(self, lib):
    """register an vamos library class"""
    self.vamos_libs[lib.get_name()] = lib
    # init lib class instance
    lib.log_call = self.log_call
    lib.log_dummy_call = self.log_dummy_call
    lib.benchmark = self.benchmark
    lib.lib_mgr = self

  def unregister_vamos_lib(self, lib):
    """unregister your vamos library class"""
    del self.vamos_libs[lib.get_name()]

  def lib_log(self, func, text, level=logging.INFO):
    """helper to create lib log messages"""
    log_libmgr.log(level, "[%10s] %s", func, text)

  # ----- common -----

  def open_dev(self, name, unit, flags, io, ctx):
    """ Open a device by name, unit and flags"""
    lib = self.open_lib(name,0,ctx)
    if lib != None:
      io.w_s("io_Device",lib.addr_base_open)
      return lib
    else:
      return None

  def close_dev(self, dev_addr, ctx):
    lib = self.close_lib(dev_addr, ctx)
    return lib

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

      # first check if its an internal vamos library
      if sane_name in self.vamos_libs:
        self.lib_log("open_lib","opening vamos lib: %s" % sane_name)
        lib = self.vamos_libs[sane_name]
        is_vamos_lib = True
      # otherwise create a new and empty AmigaLibrary
      else:
        self.lib_log("open_lib","create default lib: %s" % sane_name)
        lib_cfg = self.cfg.get_lib_config(sane_name)
        lib = AmigaLibrary(sane_name, LibraryDef, lib_cfg)
        is_vamos_lib = False

      # dump config of lib
      self._dump_lib_cfg(lib.config)

      # is lib mode = 'off' then reject open
      mode = lib.config.mode
      if mode == 'off':
        self.lib_log("open_lib","reject open: mode='off': %s" % sane_name, level=logging.WARN)
        return None

      # try to load an fd file for this lib
      lib.fd = self._load_fd(sane_name)

      # is native loading allowed?
      native_loaded = False
      native_allowed = mode in ('auto','amiga')
      if native_allowed:
        # now check if the library has a native counterpart
        # if yes then create memory layout with it
        load_name = self._get_load_lib_name(name)
        if ctx.seg_loader.can_load_seg(None,load_name):
          # setup trampoline
          tr = Trampoline(ctx,"create_lib[%s]" % sane_name)
          self._create_native_lib(lib, load_name, ctx, tr)
          self._open_native_lib(lib, ctx, tr)
          tr.final_rts()
          tr.done()
          native_loaded = True

      # no native lib available...
      # either its a vamos lib or we auto create one from an FD file
      if not native_loaded:
        # we need to have an FD file otherwise we can't create lib
        if lib.fd == None:
          self.lib_log("create_lib","can't create auto lib without FD file: %s" % sane_name, level=logging.ERROR)
          return None

        # if not 'auto' or 'vamos' then fail now
        if mode == 'amiga':
          self.lib_log("open_lib","can't open amiga lib: %s" % sane_name, level=logging.WARN)
          return None

        # create a (opt. fake/empty) vamos library
        self._create_vamos_lib(lib, ctx)
        self._register_open_lib(lib,None)
        lib.inc_usage()

    self.lib_log("open_lib","leaving open_lib(): %s -> %06x" % (lib,lib.addr_base_open), level=logging.DEBUG)
    return lib

  # return instance or null
  def close_lib(self, addr, ctx):
    # get lib object
    if addr not in self.open_libs_addr:
      self.lib_log("close_lib","No library found at address %06x" % (addr))
      return None
    lib = self.open_libs_addr[addr]
    lib.open_base_addr = addr
    self.lib_log("close_lib","Closing %s at address %06x" % (lib.name,addr))

    # native lib handling
    if lib.is_native:
      tr = Trampoline(ctx,"close_lib[%s]" % lib.name)
      self._close_native_lib(lib, addr, ctx, tr)
      if lib.ref_cnt == 0:
        pass
        # THOR: Do not release the library memory. Problem is that
        # the SAS/C go leaves references to strings to its library
        # segment pending in the QUAD: file, which then become
        # invalid if the library is removed. In reality, we should
        # only flush libs if we are low on memory.
        #  self._free_native_lib(lib, ctx, tr)
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
        self._unregister_open_lib(lib,None)
        self._free_vamos_lib(lib, ctx)
      elif lib.ref_cnt < 0:
        raise VamosInternalError("CloseLib: invalid ref count?!")

    return lib

  # ----- post-open setup -----

  def _register_open_lib(self, lib, libbase):
    # now register lib
    self.open_libs_addr[lib.addr_base] = lib
    # own base per open?
    if libbase != None and lib.addr_base != libbase:
      self.open_libs_addr[libbase] = lib
      lib.addr_base_open = libbase
    else:
      lib.addr_base_open = lib.addr_base
    self.open_libs_name[lib.name] = lib

  def _unregister_open_lib(self, lib, libbase):
    # we never really flush libraries, unless the library
    # builds its own libbase on each invocation.
    # unregister lib
    #del self.open_libs_addr[lib.addr_base]
    # own base per open?
    if libbase != None and libbase != lib.addr_base:
      del self.open_libs_addr[libbase]
    #del self.open_libs_name[lib.name]

  # ----- open/close native lib -----

  def _open_native_lib(self, lib, ctx, tr):
    """call Open() on native lib"""
    lib_base = lib.addr_base
    if lib_base != 0:
      # RTF_AUTOINIT lib already knows the lib_base and the open vector
      open_addr = lib.vectors[0]
      self.lib_log("open_lib","trampoline: open @%06x (lib_base/a6=%06x)" % (open_addr,lib_base), level=logging.DEBUG)
    else:
      # RT_INIT lib does not know address yet - will be patched later
      open_addr = 0
      self.lib_log("open_lib","trampoline: open - needs patch", level=logging.DEBUG)
    tr.save_all_but_d0()
    # we save an offset to lib_base patching later on
    lib.patch_off_open = tr.get_code_offset()
    tr.set_ax_l(6, lib_base)
    tr.jsr(open_addr)
    # fetch the result (the lib base might have been altered)
    def trap_open_native_lib():
      self._open_native_lib_part2(lib, ctx)
    tr.trap(trap_open_native_lib)
    tr.restore_all_but_d0()

    # update ref count
    lib.ref_cnt += 1
    return lib

  def _open_native_lib_part2(self, lib, ctx):
    lib.addr_base_open = ctx.cpu.r_reg(REG_D0)
    self.lib_log("open_lib", "done opening native lib: %s -> %06x" % (lib,lib.addr_base_open), level=logging.DEBUG)
    self._register_open_lib(lib,lib.addr_base_open)

  def _close_native_lib(self, lib, lib_base, ctx, tr):
    """call Close() on native lib"""
    # add Close() call to trampoline
    close_addr = ctx.mem.access.r32(lib_base - 10) # LVO_Close
    lib.addr_base_open = lib_base
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
    self._unregister_open_lib(lib,lib.addr_base_open)
    self.lib_log("close_lib", "done closing native lib: %s seg_list=%06x" % (lib, result), level=logging.DEBUG)

  # ----- create/free native lib -----

  def _create_native_lib(self, lib, load_name, ctx, tr):
    """load native lib from binary file and allocate memory"""

    # use seg_loader to load lib
    self.lib_log("load_lib","loading native lib: %s" % load_name)
    lib.seg_list = ctx.seg_loader.load_seg(None,load_name)
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
      self.lib_log("load_lib","No single resident in %s found!" % load_name, level=logging.ERROR)
      return None

    # make sure its a library
    res = res_list[0]
    if res['type'] != AmigaResident.NT_DEVICE and res['type'] != AmigaResident.NT_LIBRARY:
      self.lib_log("load_lib","Resident is not a library nor a device!", level=logging.ERROR)
      return None

    # resident is ok
    lib_name = res['name']
    lib_id = res['id']
    lib.mem_version = res['version']
    lib.auto_init = res['auto_init']
    init_ptr = res['init_ptr']
    self.lib_log("load_lib", "found resident: name='%s' id='%s' auto_init=%s init_ptr=%08x in %.4fs"
      % (lib_name, lib_id, lib.auto_init, init_ptr, delta), level=logging.DEBUG)

    # has RTF_AUTOINIT?
    if lib.auto_init:
      if not self._auto_init_native_lib(lib, ar, res, ctx, tr):
        return None
    # or has RT_INIT?
    elif init_ptr != 0:
      self._rtinit_native_lib(lib, ctx, tr, init_ptr)
    # hmm, no RTF_AUTOINIT and no RT_INIT?
    else:
      self.lib_log("load_lib", "neither RTF_AUTOINIT nor RT_INIT found!", level=logging.ERROR)
      return None

    return lib

  def _rtinit_native_lib(self, lib, ctx, tr, init_ptr):
    """library init done for RT_INIT style lib"""
    exec_base = ctx.mem.access.r32(4)
    seg_list = lib.seg_list.b_addr
    tr.save_all()
    tr.set_dx_l(0, 0) # D0=0
    tr.set_ax_l(0, seg_list) # A0 = SegList
    tr.set_ax_l(6, exec_base) # A6 = ExecBase
    tr.jsr(init_ptr)
    def trap_init_done():
      self._rtinit_done_native_lib(lib, ctx)
    tr.trap(trap_init_done)
    tr.restore_all()
    self.lib_log("load_lib", "trampoline: RT_INIT @%06x (d0=0 seg_list/a0=%06x exec_base/a6=%06x)" % \
      (init_ptr, seg_list, exec_base), level=logging.DEBUG)
    # DEBUG
    addr = seg_list << 2
    sl_len = ctx.mem.access.r32(addr-4)
    sl_next = ctx.mem.access.r32(addr)
    self.lib_log("load_lib", "seglist: len=%d next=%4x" % (sl_len, sl_next))
    self.lib_log("load_lib", "seglist: %s" % lib.seg_list)

  def _rtinit_done_native_lib(self, lib, ctx):
    lib_base = ctx.cpu.r_reg(REG_D0)
    self.lib_log("load_lib", "RT_INIT done: d0=%08x" % lib_base, level=logging.DEBUG)
    #sys.exit(1)

  def _auto_init_native_lib(self, lib, ar, res, ctx, tr):
    # read auto init infos
    if not ar.read_auto_init_data(res, ctx.mem):
      self.lib_log("load_lib","Error reading auto_init!", level=logging.ERROR)
      return False

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
      seg_list = lib.seg_list.b_addr
      exec_base = ctx.mem.access.r32(4)
      lib_base = lib.addr_base
      tr.save_all()
      tr.set_dx_l(0, lib_base)
      tr.set_ax_l(0, seg_list) # baddr!
      tr.set_ax_l(6, exec_base)
      tr.jsr(init_addr)
      tr.restore_all()
      def trap_create_native_lib():
        self._auto_init_done_native_lib(lib, ctx)
      tr.trap(trap_create_native_lib)
      self.lib_log("load_lib", "trampoline: init @%06x (lib_base/d0=%06x seg_list/a0=%06x exec_base/a6=%06x)" % \
        (init_addr, lib_base, seg_list, exec_base), level=logging.DEBUG)
    else:
      self._create_native_lib_part2(lib, ctx)

    return True

  def _auto_init_done_native_lib(self, lib, ctx):
    self.lib_log("load_lib", "done loading native lib: %s" % lib)
    # Set up lib_Node
    lib.lib_access.w_s("lib_Node.ln_Succ", lib.addr_base)
    lib.lib_access.w_s("lib_Node.ln_Pred", lib.addr_base)

  def _set_all_vectors(self, mem, base_addr, vectors):
    """set all library vectors to valid addresses"""
    addr = base_addr - 6
    for v in vectors:
      mem.access.w16(addr,self.op_jmp)
      mem.access.w32(addr+2,v)
      addr -= 6

  def _free_native_lib(self, lib, ctx, tr):
    # get expunge func
    exec_base = ctx.mem.access.r32(4)
    lib_base = lib.addr_base
    expunge_addr = ctx.mem.access.r32(lib_base - 16) # LVO_Expunge
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

  # ----- vamos memory lib creation without loading a binary lib first -----

  def _create_vamos_lib(self, lib, ctx):
    """create an vamos library structure in memory for the given lib"""
    self.lib_log("create_lib","creating vamos mem lib for %s" % lib.name)
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

  def _free_vamos_lib(self, lib, ctx):
    """free memory foot print of vamos allocated library"""
    self.lib_log("free_lib","vamos mem library %s is finishing" % lib.name)

    # first call finish lib
    lib.finish_lib(ctx)
    # free memory allocation
    lib.free_lib_base(ctx)

    self.lib_log("free_lib","vamos mem library %s is free()ed" % lib.name)

  # ----- Helpers -----

  def _load_fd(self, lib_name):
    """try to load a fd file for a library from vamos data dir"""
    if lib_name.endswith(".device"):
      is_dev  = True
      fd_name = lib_name.replace(".device","_lib.fd")
    else:
      is_dev  = False
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
        if is_dev:
          fd.add_call("BeginIO",30,["IORequest"],["a1"])
          fd.add_call("AbortIO",36,["IORequest"],["a1"])
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

  def _dump_lib_cfg(self, lib_cfg):
    for key in lib_cfg._keys:
      self.lib_log("config","%s = %s" % (key, getattr(lib_cfg, key)))
