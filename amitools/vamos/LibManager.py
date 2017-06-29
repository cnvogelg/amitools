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

  def shutdown(self, ctx):
    """called from the shutdown trap after process execution to clean up libs.
       mainly used to expunge native libs with expunge type "shutdown".
       additionally force close libs that are still not closed due to invalid
       ref counts"""
    self.lib_log("shutdown","expunging native libs and check for orphaned libs")
    self.expunge_libs(ctx)

    # check for orphaned libs
    libs = self.open_libs_name.values()
    for lib in libs:

      # check ref_cnt of lib: base libs are still open, but others should be closed
      ref_cnt = lib.ref_cnt
      if lib.is_base:
        if ref_cnt != 1:
          self.lib_log("shutdown","library ref count mismatch: '%s' #%d" % (lib.name, ref_cnt),
            level=logging.WARN)
        ref_cnt -= 1
      else:
        if ref_cnt != 0:
          self.lib_log("shutdown","library ref count mismatch: '%s' #%d" % (lib.name, ref_cnt),
            level=logging.WARN)

      # try to close lib now
      if ref_cnt > 0:
        if lib.is_native:
          self._force_close_native_lib(lib, ctx)
        else:
          self._force_close_vamos_lib(lib, ctx)

  def expunge_libs(self, ctx):
    self.lib_log("expunge","expunge native libs")
    libs = self.open_libs_name.values()
    for lib in libs:
      if lib.is_native and lib.ref_cnt == 0:
        self._expunge_native_lib(lib, ctx)

  # ----- common -----

  def open_dev(self, name, unit, flags, io, ctx):
    """ Open a device by name, unit and flags"""
    lib = self.open_lib(name,0,ctx)
    if lib != None:
      io.w_s("io_Device",lib.addr_base)
      return lib
    else:
      return None

  def close_dev(self, dev_addr, ctx):
    lib = self.close_lib(dev_addr, ctx)
    return lib

  def open_lib(self, name, ver, ctx):
    """open a new library in memory
       return new AmigaLibrary instance that is setup or None if lib was not found

        name = string given to OpenLibrary and may contain path prefix
          e.g. libs/bla.library or libs:foo/bla.library

       Note: may prepare a trampoline to finish operation!
    """

    # sanitize lib name, i.e. strip path component
    # e.g. libs/bla.library -> bla.library
    sane_name = self._get_sane_lib_name(name)

    # is lib already opened?
    if sane_name in self.open_libs_name:
      lib = self.open_libs_name[sane_name]
      self.lib_log("open_lib","opening already open lib: %s ref_cnt=%d" % (sane_name, lib.ref_cnt))
      if lib.is_native:
        self._open_native_lib(lib, ctx)
      else:
        # vamos lib open: inc usage
        lib.inc_usage()

    # lib has to be openend
    else:

      # get lib config
      # first search with original name and then sane_name without path
      # finally resort to the default config (*.library)
      lib_cfg = self.cfg.get_lib_config(name, sane_name)
      self._dump_lib_cfg(name, lib_cfg)

      # depending on lib_cfg.mode decide what to do:
      mode = lib_cfg.mode
      if mode == 'off':
        # config disabled lib -> so abort OpenLibrary()
        self.lib_log("open_lib","reject open: mode='off': %s" % name, level=logging.WARN)
        lib = None
      elif mode == 'auto':
        # auto (default) tries to open internal vamos lib first and if that
        # fails tries a native amige lib
        lib = self._open_vamos_internal_lib(sane_name, ctx)
        if lib == None:
          lib = self._load_and_open_native_lib(name, sane_name, lib_cfg, ctx)
          if lib == None:
            self.lib_log("open_lib","auto found neither vamos nor amiga lib: %s" % name)
      elif mode == 'vamos':
        # only try to find an internal vamos lib
        lib = self._open_vamos_internal_lib(sane_name, ctx)
        if lib == None:
          self.lib_log("open_lib","no vamos lib found: %s" % name)
      elif mode == 'amiga':
        # only try to open an amiga lib
        lib = self._load_and_open_native_lib(name, sane_name, lib_cfg, ctx)
        if lib == None:
          self.lib_log("open_lib","no amiga lib found: %s" % name)
      elif mode == 'fake':
        # create a fake lib for this library
        lib = self._open_vamos_fake_lib(sane_name, lib_cfg, ctx)
        if lib == None:
          self.lib_log("open_lib","fake lib failed for: %s" % name)

    if lib != None:
      self.lib_log("open_lib","leaving open_lib(): %s" % lib, level=logging.DEBUG)
    else:
      self.lib_log("open_lib","leaving open_lib(): no lib!", level=logging.DEBUG)
    return lib

  # return instance or null
  def close_lib(self, addr, ctx):
    # get lib object
    if addr not in self.open_libs_addr:
      self.lib_log("close_lib","no library found at address %06x" % (addr), level=logging.ERROR)
      return None
    lib = self.open_libs_addr[addr]
    lib.open_base_addr = addr
    self.lib_log("close_lib","closing %s at address %06x" % (lib.name,addr), level=logging.DEBUG)

    # close amiga lib
    if lib.is_native:
      self._close_native_lib(lib, addr, ctx)
    # close vamos lib
    else:
      self._close_vamos_lib(lib, ctx)

    return lib

  # ----- vamos lib -----

  def _open_vamos_internal_lib(self, sane_name, ctx):
    """try to open an internal vamos lib
       return internal lib or None if not found"""
    self.lib_log("open_lib","trying to open vamos lib: '%s'" % sane_name)
    if sane_name not in self.vamos_libs:
      return None

    self.lib_log("open_lib","found vamos lib: %s" % sane_name)
    lib = self.vamos_libs[sane_name]

    return self._open_vamos_lib(sane_name, lib, ctx)

  def _open_vamos_fake_lib(self, sane_name, lib_cfg, ctx):
    """try to setup a fake lib from a given .fd file
       return new lib or None if creation failed"""

    # create empty lib
    lib = AmigaLibrary(sane_name, LibraryDef, lib_cfg)

    return self._open_vamos_lib(sane_name, lib, ctx)

  def _open_vamos_lib(self, sane_name, lib, ctx):
    # now we need an fd file to know about the structure of the lib
    lib.fd = self._load_fd(sane_name)
    if lib.fd == None:
      self.lib_log("create_lib","can't create vamos lib without FD file: %s" % sane_name, level=logging.ERROR)
      return None

    # fill in structure from fd
    self._create_vamos_lib(lib, ctx)

    # register mappings in manager
    self._register_lib_name(lib)
    self._register_lib_base(lib, lib.addr_base)

    # usage count update
    lib.inc_usage()

    return lib

  def _close_vamos_lib(self, lib, ctx):
    self.lib_log("close_lib","closing vamos lib '%s' ref_cnt: %d" % (lib.name, lib.ref_cnt))
    # decrement usage
    lib.dec_usage()
    # not used any more
    if lib.ref_cnt == 0:
      self.lib_log("close_lib","freeing vamos lib '%s'" % (lib.name))

      # unregister mappings in manager
      self._unregister_lib_name(lib)
      self._unregister_lib_base(lib, lib.addr_base)

      # finally free lib
      self._free_vamos_lib(lib, ctx)
    elif lib.ref_cnt < 0:
      raise VamosInternalError("CloseLib: invalid ref count?!")

  def _force_close_vamos_lib(self, lib, ctx):
    self.lib_log("close_lib","force closing vamos lib '%s' ref_cnt: %d" % (lib.name, lib.ref_cnt))
    # 'fix' ref_cnt
    ref_cnt = 1
    self._close_vamos_lib(lib, ctx)

  # ----- manage lib maps -----

  def _register_lib_name(self, lib):
    self.lib_log("map_lib","register lib name: %s" % lib.name, level=logging.DEBUG)
    self.open_libs_name[lib.name] = lib

  def _unregister_lib_name(self, lib):
    self.lib_log("map_lib","unregister lib name: %s" % lib.name, level=logging.DEBUG)
    del self.open_libs_name[lib.name]

  def _register_lib_base(self, lib, lib_base):
    self.lib_log("map_lib","register lib base: %s -> @%08lx" % (lib.name, lib_base), level=logging.DEBUG)
    self.open_libs_addr[lib_base] = lib

  def _unregister_lib_base(self, lib, lib_base):
    self.lib_log("map_lib","unregister lib base: %s -> @%08lx" % (lib.name, lib_base), level=logging.DEBUG)
    del self.open_libs_addr[lib_base]

  # ----- open native lib -----

  def _load_and_open_native_lib(self, name, sane_name, lib_cfg, ctx):
    """try to load and open native lib
       return new lib instance or None if lib was not found"""

    # create empty lib
    lib = AmigaLibrary(sane_name, LibraryDef, lib_cfg)

    # determine file name from open_name, i.e. prepend LIBS: if no path is found
    load_name = self._get_load_lib_name(name)
    self.lib_log("load_lib","trying to load amiga lib: '%s'" % load_name, level=logging.INFO)

    # pick current dir lock if available
    # this allows to resolve relative paths given in load_name
    cur_dir_lock = None
    proc = ctx.process
    if proc is not None:
      cur_dir_lock = proc.cwd_lock

    # is native lib available in file system?
    if ctx.seg_loader.can_load_seg(cur_dir_lock, load_name, local_path=True):
      self.lib_log("load_lib","found amiga lib: '%s'" % load_name)

      # setup trampoline
      tr = Trampoline(ctx,"create_lib[%s]" % sane_name)
      self._create_native_lib(lib, load_name, ctx, tr, cur_dir_lock)
      self._open_native_lib_int(lib, ctx, tr)
      tr.final_rts()
      tr.done()

      # do we have an optional fd file for this lib?
      lib.fd = self._load_fd(sane_name)

      self._register_lib_name(lib)

      return lib
    else:
      return None

  def _open_native_lib(self, lib, ctx):
    # call Open()
    tr = Trampoline(ctx,"open_lib[%s]" % sane_name)
    self._open_native_lib_int(lib, ctx, tr)
    tr.final_rts()
    tr.done()

  def _open_native_lib_int(self, lib, ctx, tr):
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
    lib_base = ctx.cpu.r_reg(REG_D0)
    if lib.add_lib_base(lib_base):
      self._register_lib_base(lib, lib_base)
    self.lib_log("open_lib", "done opening native lib: %s -> %06x" % (lib, lib_base), level=logging.DEBUG)

  # ----- close native lib -----

  def _force_close_native_lib(self, lib, ctx):
    lib_bases = lib.get_all_lib_bases()
    txt = ",".join(map(lambda x : "%08x" % x, lib_bases))
    self.lib_log("close_lib","force closing native lib: '%s' ref_cnt: %d bases=%s" %
      (lib.name, lib.ref_cnt, txt))
    for lib_base in lib_bases:
      self._close_native_lib(lib, lib_base, ctx)

  def _close_native_lib(self, lib, lib_base, ctx):
    self.lib_log("close_lib","closing native lib: '%s' ref_cnt: %d" % (lib.name, lib.ref_cnt))
    tr = Trampoline(ctx,"close_lib[%s]" % lib.name)
    self._close_native_lib_int(lib, lib_base, ctx, tr)
    if lib.ref_cnt == 0:
      # lib has no users and can be expunged/removed
      expunge_mode = lib.config.expunge
      if expunge_mode == 'last_close':
        self.lib_log("close_lib","expunging native lib: '%s'" % lib.name)
        # do it now
        self._free_native_lib(lib, ctx, tr)
    elif lib.ref_cnt < 0:
      raise VamosInternalError("CloseLib: invalid ref count?!")
    tr.final_rts()
    tr.done()

  def _expunge_native_lib(self, lib, ctx):
    self.lib_log("expunge", "expunging native lib: '%s'" % lib.name)
    tr = Trampoline(ctx,"expunge_lib[%s]" % lib.name)
    self._free_native_lib(lib, ctx, tr)
    tr.final_rts()
    tr.done()

  def _close_native_lib_int(self, lib, lib_base, ctx, tr):
    """call Close() on native lib"""
    # add Close() call to trampoline
    close_addr = ctx.mem.access.r32(lib_base - 10) # LVO_Close

    # remove this lib_base addr
    if lib.del_lib_base(lib_base):
      self._unregister_lib_base(lib, lib_base)

    self.lib_log("close_lib","trampoline: close @%06x (lib_base/a6=%06x)" % (close_addr, lib_base), level=logging.DEBUG)
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
    self.lib_log("close_lib", "done closing native lib: %s seg_list=%06x" % (lib, result), level=logging.DEBUG)

  # ----- create/free native lib -----

  def _create_native_lib(self, lib, load_name, ctx, tr, cur_dir_lock=None):
    """load native lib from binary file and allocate memory"""

    # use seg_loader to load lib
    self.lib_log("load_lib","loading native lib: %s" % load_name)
    lib.seg_list = ctx.seg_loader.load_seg(cur_dir_lock,load_name,local_path=True)
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

    # unregister name
    self._unregister_lib_name(lib)

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

  def _dump_lib_cfg(self, lib_name, lib_cfg):
    items = ["for_lib='%s'" % lib_name, "use_cfg='%s'" % lib_cfg.name]
    for key in lib_cfg._keys:
      items.append("%s=%s" % (key, getattr(lib_cfg, key)))
    self.lib_log("config_lib", " ".join(items))
