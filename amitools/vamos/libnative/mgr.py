from amitools.vamos.Log import log_libmgr
from amitools.vamos.atypes import Library
from .loader import LibLoader
from .libfuncs import LibFuncs


class NativeLibManager(object):
  def __init__(self, machine, alloc, path_mgr, segloader=None):
    self.loader = LibLoader(machine, alloc, segloader)
    self.funcs = LibFuncs(machine, alloc)
    self.path_mgr = path_mgr
    self.mem = machine.get_mem()
    # state
    self.addr_name = {}

  def is_lib_addr(self, addr):
    return addr in self.addr_name

  def get_lib_addr_for_name(self, name):
    return self.funcs.find_library(name)

  def shutdown(self, run_sp=None):
    """return number of libs still left unexpunged"""
    return self.expunge_libs(run_sp)

  def expunge_libs(self, run_sp=None):
    """return number of libs still left unexpunged"""
    log_libmgr.info("[native] +expunge_libs")
    left_libs = 0
    for base_addr in dict(self.addr_name):
      seglist = self.expunge_lib(base_addr, run_sp)
      if not seglist:
        left_libs += 1
    log_libmgr.info("[native] -expunge_libs: %d left", left_libs)
    return left_libs

  def expunge_lib(self, base_addr, run_sp=None):
    if not base_addr in self.addr_name:
      raise ValueError("expunge_lib: unknown base %06x" % base_addr)
    seglist = self.funcs.rem_library(base_addr, run_sp)
    log_libmgr.info("[native] expunge_lib @%06x", base_addr)
    if seglist:
      name = self.addr_name[base_addr]
      del self.addr_name[base_addr]
      log_libmgr.info(" -> '%s', seglist=%06x", name, seglist)
    return seglist

  def open_lib(self, lib_name, lock=None, run_sp=None):
    log_libmgr.info("[native] +open_lib: lib_name='%s'", lib_name)
    # extract lib base name
    base_name = self.loader.get_lib_base_name(lib_name)
    # find library
    lib_base = self.funcs.find_library(base_name)
    log_libmgr.info("find: '%s' -> @%06x", base_name, lib_base)
    # not found... try to load it
    if lib_base == 0:
      lib_base, seglist, sys_path, ami_path = self.loader.load_lib_name(
          self.path_mgr, lib_name, lock, run_sp)
      # even loading failed... abort
      if lib_base == 0:
        log_libmgr.info("load: failed!")
        return 0
      log_libmgr.info("load: @%06x  %s  sys='%s' ami='%s'",
          lib_base, seglist, sys_path, ami_path)
    # got lib: open lib... may return new base!
    lib_base = self.funcs.open_library(lib_base, run_sp)
    # store (new) base addr and name
    if lib_base != 0:
      lib = Library(self.mem, lib_base)
      lib_name = lib.node.name
      self.addr_name[lib_base] = lib_name
    log_libmgr.info("[native] -open_lib: lib_base=@%06x", lib_base)
    # return base
    return lib_base

  def close_lib(self, base_addr, run_sp=None):
    if not base_addr in self.addr_name:
      raise ValueError("close_lib: unknown base %06x" % base_addr)
    log_libmgr.info("[native] close_lib: @%06x", base_addr)
    seglist = self.funcs.close_library(base_addr, run_sp)
    if seglist:
      name = self.addr_name[base_addr]
      del self.addr_name[base_addr]
      log_libmgr.info(" -> '%s', seglist=%06x", name, seglist)
    return seglist
