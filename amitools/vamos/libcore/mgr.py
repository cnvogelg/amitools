import datetime
import logging
from amitools.vamos.log import log_lib, log_libmgr
from amitools.vamos.libcore import LibCreator, LibInfo, LibRegistry, LibCtxMap, LibProfiler
from amitools.vamos.atypes import ExecLibrary


class VLibManager(object):
  """handle a set of vlib instances"""

  def __init__(self, machine, alloc,
               profiler_cfg=None):
    self.machine = machine
    self.mem = machine.get_mem()
    self.alloc = alloc
    self.lib_reg = LibRegistry()
    self.ctx_map = LibCtxMap(machine)
    self.profiler = LibProfiler(profiler_cfg)
    # tools
    self._setup_creator()
    # state
    self.exec_lib = None
    self.addr_vlib = {}
    self.name_vlib = {}

  def _setup_creator(self):
    # tools
    log_missing = None
    log_valid = None
    if log_lib.isEnabledFor(logging.WARNING):
      log_missing = log_lib
    if log_lib.isEnabledFor(logging.INFO):
      log_valid = log_lib
    self.creator = LibCreator(self.alloc, self.machine.get_traps(),
                              log_missing=log_missing, log_valid=log_valid,
                              profiler=self.profiler)

  def add_impl_cls(self, name, impl_cls):
    self.lib_reg.add_lib_impl(name, impl_cls)

  def add_ctx(self, name, ctx):
    self.ctx_map.add_ctx(name, ctx)

  def bootstrap_exec(self, exec_info=None,
                     version=0, revision=0):
    """setup exec library"""
    if exec_info is None:
      date = datetime.date(day=7, month=7, year=2007)
      exec_info = LibInfo('exec.library', version, revision, date)
    # make sure its an exec info
    assert exec_info.get_name() == 'exec.library'
    # create vlib
    vlib = self._create_vlib(exec_info, False)
    assert vlib
    assert vlib.impl
    # setup exec_lib
    lib_base = vlib.get_library().get_addr()
    self.exec_lib = ExecLibrary(self.mem, lib_base)
    # store lib base
    self.mem.w32(4, lib_base)
    self.machine.set_zero_mem(0, lib_base)
    # with exec_lib in place we can add exec's vlib
    self._add_vlib(vlib)
    # inc exec's open cnt so lib gets never expunged
    self.exec_lib.lib_node.inc_open_cnt()
    return vlib

  def get_vlib_by_addr(self, addr):
    """return associated vlib for a base lib address"""
    if addr in self.addr_vlib:
      return self.addr_vlib[addr]

  def get_vlib_by_name(self, name):
    """return associated vlib for a name"""
    if name in self.name_vlib:
      return self.name_vlib[name]

  def get_profiler(self):
    """return the lib profiler"""
    return self.profiler

  def shutdown(self):
    """cleanup libs

    try to expunge all libs and report still open ones
    """
    log_libmgr.info("[vamos] +shutdown")
    # dec exec's open cnt
    self.exec_lib.lib_node.dec_open_cnt()
    # now expunge all libs
    left_libs = self.expunge_libs()
    left_devs = self.expunge_devs()
    log_libmgr.info("[vamos] +shutdown: left libs=%d, devs=%d",
                    left_libs, left_devs)
    # finally shutdown profiler
    self.profiler.shutdown()
    return left_libs + left_devs

  def expunge_libs(self):
    """expunge all unused vlibs

       return number of libs _not_ expunged
    """
    return self._expunge_list(self.exec_lib.lib_list)

  def expunge_devs(self):
    """expunge all unused vlibs

       return number of libs _not_ expunged
    """
    return self._expunge_list(self.exec_lib.device_list)

  def _expunge_list(self, node_list):
    left_libs = 0
    for node in node_list:
      lib_base = node.get_addr()
      # is it a vlib?
      if lib_base in self.addr_vlib:
        vlib = self.addr_vlib[lib_base]
        if not self.expunge_lib(vlib):
          left_libs += 1
    return left_libs

  def expunge_lib(self, vlib):
    """expunge a vlib"""
    lib = vlib.get_library()
    # still open?
    if lib.open_cnt > 0:
      return False
    # vlib?
    self._rem_vlib(vlib)
    return True

  def make_lib_name(self, name, version=0, revision=0, fake=False):
    date = datetime.date(day=7, month=7, year=2007)
    info = LibInfo(name, version, revision, date)
    return self.make_lib(info, fake)

  def make_lib(self, lib_info, fake=False):
    vlib = self._create_vlib(lib_info, fake)
    if vlib:
      self._add_vlib(vlib)
    return vlib

  def open_lib_name(self, name, version=0, revision=0, fake=False):
    vlib = self.get_vlib_by_name(name)
    if not vlib:
      vlib = self.make_lib_name(name, version, revision, fake)
    if vlib:
      vlib.open()
    return vlib

  def open_lib(self, lib_info, fake=False):
    vlib = self.get_vlib_by_name(name)
    if not vlib:
      vlib = self.make_lib(lib_info, fake, is_dev)
    if vlib:
      vlib.open()
    return vlib

  def close_lib(self, vlib):
    vlib.close()
    return self.expunge_lib(vlib)

  def _create_vlib(self, lib_info, fake):
    # get lib ctx
    name = lib_info.get_name()
    ctx = self.ctx_map.get_ctx(name)
    # get impl
    if fake:
      impl = None
    else:
      name = lib_info.get_name()
      impl_cls = self.lib_reg.get_lib_impl(name)
      if impl_cls:
        impl = impl_cls()
        # adjust version?
        if lib_info.version == 0:
          lib_info.version = impl.get_version()
      else:
        return None
    # create lib
    vlib = self.creator.create_lib(lib_info, ctx, impl)
    # store vlib in context
    ctx.vlib = vlib
    return vlib

  def _add_vlib(self, vlib):
    addr = vlib.get_addr()
    name = vlib.get_name()
    # store internally
    self.addr_vlib[addr] = vlib
    self.name_vlib[name] = vlib
    # add lib to exec lib list
    lib = vlib.get_library()
    if vlib.is_device():
      self.exec_lib.device_list.enqueue(lib.node)
    else:
      self.exec_lib.lib_list.enqueue(lib.node)

  def _rem_vlib(self, vlib):
    addr = vlib.get_addr()
    name = vlib.get_name()
    # remove internally
    del self.addr_vlib[addr]
    del self.name_vlib[name]
    # remove from exec lib list
    lib = vlib.get_library()
    lib.node.remove()
    # free vlib
    vlib.free()
