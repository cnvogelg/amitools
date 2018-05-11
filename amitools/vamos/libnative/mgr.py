from amitools.vamos.Log import log_libmgr
from amitools.vamos.atypes import Library
from .loader import LibLoader
from .libfuncs import LibFuncs


class ALibInfo(object):
  def __init__(self, name, base_addr, seglist_baddr):
    self.name = name
    self.base_addr = base_addr
    self.seglist_baddr = seglist_baddr
    self.multi_bases = []

  def __str__(self):
    multis = ",".join(map(lambda x: "%06x" % x, self.multi_bases))
    return "['%s':@%06x,seglist=%06x,multis=%s]" % \
        (self.name, self.base_addr, self.seglist_baddr, multis)

  def get_name(self):
    return self.name

  def get_base_addr(self):
    return self.base_addr

  def get_seglist_baddr(self):
    return self.seglist_baddr

  def add_base_addr(self, base_addr):
    self.multi_bases.append(base_addr)

  def is_lib_addr(self, addr, with_multis=True):
    if addr == self.base_addr:
      return True
    if with_multis:
      for multi in self.multi_bases:
        if multi == addr:
          return True
    return False


class ALibManager(object):
  def __init__(self, machine, alloc, path_mgr, segloader=None):
    self.loader = LibLoader(machine, alloc, segloader)
    self.funcs = LibFuncs(machine, alloc)
    self.path_mgr = path_mgr
    self.mem = machine.get_mem()
    # state
    self.lib_infos = []

  def is_lib_addr(self, addr, with_multis=True):
    """check if a given addr is the lib base of a native lib

       includes both original base addr and mult instance bases"""
    for info in self.lib_infos:
      if info.is_lib_addr(addr):
        return True
    return False

  def get_lib_addr_for_name(self, name):
    """return the (original loaded) base addr of lib given by name"""
    for info in self.lib_infos:
      if info.get_name() == name:
        return info.get_base_addr()
    return 0

  def shutdown(self, run_sp=None):
    """return number of libs still left unexpunged"""
    return self.expunge_libs(run_sp)

  def expunge_libs(self, run_sp=None):
    """return number of libs still left unexpunged"""
    log_libmgr.info("[native] +expunge_libs")
    left_libs = 0
    for lib_info in self.lib_infos:
      base_addr = lib_info.get_base_addr()
      seglist = self.expunge_lib(base_addr, run_sp)
      if not seglist:
        left_libs += 1
    log_libmgr.info("[native] -expunge_libs: %d left", left_libs)
    return left_libs

  def expunge_lib(self, base_addr, run_sp=None):
    log_libmgr.info("[native] +expunge_lib: base=@%06x", base_addr)
    if not self.is_lib_addr(base_addr, False):
      raise ValueError("expunge_lib: invalid lib_base=%06x" % base_addr)
    seglist = self.funcs.rem_library(base_addr, run_sp)
    if seglist:
      self._rem_info(base_addr, seglist)
    log_libmgr.info("[native] -expunge_lib: seglist=%06x", seglist)
    return seglist

  def close_lib(self, base_addr, run_sp=None):
    log_libmgr.info("[native] +close_lib: base=@%06x", base_addr)
    if not self.is_lib_addr(base_addr, True):
      raise ValueError("close_lib: invalid lib_base=%06x" % base_addr)
    seglist = self.funcs.close_library(base_addr, run_sp)
    if seglist:
      self._rem_info(base_addr, seglist)
    log_libmgr.info("[native] -close_lib: seglist=%06x", seglist)
    return seglist

  def open_lib(self, lib_name, lock=None, run_sp=None):
    log_libmgr.info("[native] +open_lib: lib_name='%s'", lib_name)
    # multict lib base name
    base_name = self.loader.get_lib_base_name(lib_name)
    # find library
    lib_info = self._find_info(base_name)
    log_libmgr.info("find: '%s' -> %s", base_name, lib_info)
    # not found... try to load it
    if not lib_info:
      log_libmgr.info("loading native lib: '%s'", lib_name)
      lib_base, seglist, sys_path, ami_path = self.loader.load_lib_name(
          self.path_mgr, lib_name, lock, run_sp)
      # even loading failed... abort
      if lib_base == 0:
        log_libmgr.info("[native] -open_lib: load failed!")
        return 0
      log_libmgr.info("loaded: @%06x  %s", lib_base, seglist)
      log_libmgr.info("loaded: path sys='%s' ami='%s'", sys_path, ami_path)
      # store original base addr and name in info
      lib_info = self._add_info(base_name, lib_base, seglist.get_baddr())
    else:
      lib_base = lib_info.get_base_addr()
    # got lib: open lib... may return new base!
    org_base = lib_base
    lib_base = self.funcs.open_library(org_base, run_sp)
    if lib_base != org_base:
      # multi instance base will be added
      lib_info.add_base_addr(lib_base)
    log_libmgr.info("[native] -open_lib: org_base=@%06x, lib_base=@%06x, %s",
                    org_base, lib_base, lib_info)
    # return base
    return lib_base

  def _find_info(self, base_name):
    for info in self.lib_infos:
      if info.get_name() == base_name:
        return info

  def _add_info(self, base_name, lib_base, seglist_baddr):
    lib_info = ALibInfo(base_name, lib_base, seglist_baddr)
    self.lib_infos.append(lib_info)
    return lib_info

  def _rem_info(self, base_addr, seglist_baddr):
    for info in self.lib_infos:
      if info.get_base_addr() == base_addr:
        break
    assert info
    assert info.get_seglist_baddr() == seglist_baddr
    self.lib_infos.remove(info)
