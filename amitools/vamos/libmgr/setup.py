from amitools.vamos.libcore import LibProfilerConfig
from amitools.vamos.lib.lexec.ExecLibCtx import ExecLibCtx
from amitools.vamos.lib.dos.DosLibCtx import DosLibCtx
from amitools.vamos.lib.LibList import vamos_libs
from amitools.vamos.loader import SegmentLoader
from amitools.vamos.log import log_libmgr
from .cfg import LibMgrCfg
from .mgr import LibManager


class SetupLibManager(object):
  def __init__(self, machine, mem_map, path_mgr, lib_cfg=None, profiler_cfg=None):
    self.machine = machine
    self.mem_map = mem_map
    self.path_mgr = path_mgr
    self.alloc = mem_map.get_alloc()
    self.lib_mgr_cfg = lib_cfg
    self.profiler_cfg = profiler_cfg
    # state
    self.seg_loader = None
    self.exec_ctx = None
    self.dos_ctx = None
    self.lib_mgr = None

  def parse_config(self, main_cfg):
    if not main_cfg:
      return True
    cfg = main_cfg.get_profile_dict().profile
    self.parse_profiler_cfg(cfg)
    cfg = main_cfg.get_libs_dict()
    self.parse_lib_mgr_cfg(cfg)
    return True

  def parse_lib_mgr_cfg(self, cfg):
    self.lib_mgr_cfg = LibMgrCfg.from_dict(cfg)

  def parse_profiler_cfg(self, cfg):
    names = cfg.libs.names
    if names:
      profiling = True
      all_libs = 'all' in names
    else:
      profiling = False
      all_libs = False
    self.profiler_cfg = LibProfilerConfig(profiling=profiling,
                                          all_libs=all_libs,
                                          libs=names,
                                          add_samples=cfg.libs.calls,
                                          file=cfg.output.file,
                                          append=cfg.output.append,
                                          dump=cfg.output.dump)

  def setup(self, vamos_legacy):
    # create def cfg
    if self.lib_mgr_cfg is None:
      self.lib_mgr_cfg = LibMgrCfg()
    # create segment loader
    self.seg_loader = SegmentLoader(self.alloc, self.path_mgr)
    # setup contexts
    self.exec_ctx = ExecLibCtx(self.machine, self.alloc,
                               self.seg_loader, self.path_mgr)
    self.dos_ctx = DosLibCtx(self.machine, self.alloc,
                             self.seg_loader, self.path_mgr,
                             vamos_legacy)
    # create lib mgr
    self.lib_mgr = LibManager(self.machine, self.alloc, self.seg_loader,
                              self.lib_mgr_cfg,
                              profiler_cfg=self.profiler_cfg)
    self.lib_mgr.add_ctx('exec.library', self.exec_ctx)
    self.lib_mgr.add_ctx('dos.library', self.dos_ctx)
    # add all vamos libs
    for name in vamos_libs:
      cls = vamos_libs[name]
      self.lib_mgr.add_impl_cls(name, cls)
    # finally bootstrap exec
    self.lib_mgr.bootstrap_exec()
    # return lib_mgr
    return self.lib_mgr

  def cleanup(self):
    # shutdown of libmgr needs temp stack
    sp = self.machine.get_ram_begin() - 4
    self.lib_mgr.shutdown(run_sp=sp)

  def open_base_libs(self):
    log_libmgr.info("opening base libs...")
    # open exec lib
    self.exec_addr = self.lib_mgr.open_lib('exec.library', 0)
    self.exec_vlib = self.lib_mgr.get_vlib_by_addr(self.exec_addr)
    self.exec_impl = self.exec_vlib.get_impl()
    log_libmgr.info("open base lib: exec: @%06x", self.exec_addr)
    # link exec to dos
    self.dos_ctx.set_exec_lib(self.exec_impl)
    # open dos lib
    self.dos_addr = self.lib_mgr.open_lib('dos.library', 0)
    self.dos_vlib = self.lib_mgr.get_vlib_by_addr(self.dos_addr)
    self.dos_impl = self.dos_vlib.get_impl()
    self.dos_ctx.set_dos_lib(self.dos_impl)
    log_libmgr.info("open base lib: dos:  @%06x", self.dos_addr)
    # set exec base @4
    log_libmgr.debug("setting execbase @4")
    self.machine.set_zero_mem(0, self.exec_addr)

  def close_base_libs(self):
    log_libmgr.info("closing base libs...")
    # close dos
    self.lib_mgr.close_lib(self.dos_addr)
    log_libmgr.info("closed dos")
    # close exec
    self.lib_mgr.close_lib(self.exec_addr)
    log_libmgr.info("closed exec")
