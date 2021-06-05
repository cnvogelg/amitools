from amitools.vamos.log import log_libmgr
from amitools.vamos.libtypes import Library
from amitools.vamos.libcore import VLibManager
from amitools.vamos.libnative import ALibManager, LibLoader
from .cfg import LibCfg
from .proxy import LibProxyManager


class LibManager(object):
    """the library manager handles both native and vamos libs"""

    def __init__(self, machine, alloc, segloader, cfg, main_profiler=None):
        self.mem = machine.get_mem()
        self.cfg = cfg
        self.machine = machine
        self.vlib_mgr = VLibManager(machine, alloc, main_profiler=main_profiler)
        self.alib_mgr = ALibManager(machine, alloc, segloader)
        self.proxy_mgr = LibProxyManager(self)
        # inject proxy mgr into all ctx
        self.vlib_mgr.set_ctx_extra_attr("proxies", self.proxy_mgr)
        cfg.dump(log_libmgr.info)

    def get_lib_proxy_mgr(self):
        """access the library proxy manager"""
        return self.proxy_mgr

    def add_ctx(self, name, ctx):
        """allow to add vlib contexts"""
        self.vlib_mgr.add_ctx(name, ctx)

    def add_impl_cls(self, name, impl_cls):
        """allow to add vlib impl classes"""
        self.vlib_mgr.add_impl_cls(name, impl_cls)

    def get_vlib_by_addr(self, addr):
        """return associated vlib for a base lib address"""
        return self.vlib_mgr.get_vlib_by_addr(addr)

    def get_vlib_by_name(self, name):
        """return associated vlib for a name"""
        return self.vlib_mgr.get_vlib_by_name(name)

    def get_alib_info_by_addr(self, addr):
        """return associated alib info for a base lib address"""
        return self.alib_mgr.is_base_addr(addr)

    def bootstrap_exec(self, exec_info=None):
        """setup exec vlib as first and essential lib"""
        version = 0
        lib_cfg = self.cfg.get_lib_cfg("exec.library")
        force_version = lib_cfg.get_force_version()
        if force_version is not None:
            version = force_version
            log_libmgr.info("exec: force version: %s", version)
        return self.vlib_mgr.bootstrap_exec(exec_info, version)

    def shutdown(self, run_sp=None):
        """cleanup libs

        try to expunge all libs and report still open ones
        """
        self.proxy_mgr.shutdown()
        log_libmgr.info("+shutdown")
        aleft = self.alib_mgr.shutdown(run_sp)
        if aleft > 0:
            log_libmgr.warning("shutdown: can't expunge %d amiga libs/devs!", aleft)
        vleft = self.vlib_mgr.shutdown()
        if vleft > 0:
            log_libmgr.warning("shutdown: can't expunge %d vamos libs/devs!", vleft)
        left = vleft + aleft
        log_libmgr.info("-shutdwon: aleft=%d, vleft=%d", aleft, vleft)
        return left

    def expunge_libs(self, run_sp=None):
        """expunge all unused libs

        return number of libs _not_ expunged
        """
        log_libmgr.info("+expunge_libs")
        aleft = self.alib_mgr.expunge_libs(run_sp)
        vleft = self.vlib_mgr.expunge_libs()
        log_libmgr.info("-expunge_libs: aleft=%d, vleft=%d", aleft, vleft)
        return vleft + aleft

    def expunge_devs(self, run_sp=None):
        """expunge all unused devs

        return number of libs _not_ expunged
        """
        log_libmgr.info("+expunge_devs")
        aleft = 0  # TBD
        vleft = self.vlib_mgr.expunge_devs()
        log_libmgr.info("-expunge_devs: aleft=%d, vleft=%d", aleft, vleft)
        return vleft

    def expunge_lib(self, addr, run_sp=None):
        """expunge a library given by base address

        return True if lib was expunged
        """
        log_libmgr.info("expunge_lib: @%06x", addr)
        vlib = self.vlib_mgr.get_vlib_by_addr(addr)
        if vlib:
            return self.vlib_mgr.expunge_lib(vlib)
        elif self.alib_mgr.is_load_addr(addr):
            seglist = self.alib_mgr.expunge_lib(addr, run_sp)
            return seglist != 0
        else:
            log_libmgr.error("expunge: unknown lib @%06x!", addr)

    def close_lib(self, addr, run_sp=None):
        """close a library

        return True if lib was expunged, too
        """
        log_libmgr.info("close_lib: @%06x", addr)
        vlib = self.vlib_mgr.get_vlib_by_addr(addr)
        if vlib:
            return self.vlib_mgr.close_lib(vlib)
        elif self.alib_mgr.is_base_addr(addr):
            seglist = self.alib_mgr.close_lib(addr, run_sp)
            return seglist != 0
        else:
            log_libmgr.error("close: unknown lib @%06x!", addr)

    def open_lib(
        self, full_name, version=0, cwd_lock=None, run_sp=None, progdir_lock=None
    ):
        """open a library

        return lib_base addr or 0
        """
        # get base name
        base_name = LibLoader.get_lib_base_name(full_name)
        log_libmgr.info(
            "open_lib: '%s' ver=%d -> base_name='%s'", full_name, version, base_name
        )
        # get lib params
        lib_cfg = self.cfg.get_cfg(full_name, base_name)
        log_libmgr.info("-> cfg: %s", lib_cfg)
        # handle mode
        mode = lib_cfg.get_create_mode()
        if mode == LibCfg.CREATE_MODE_OFF:
            return 0
        try_vlib, try_alib, fake = self._map_mode(mode)

        # try vamos first
        addr = 0
        vlib = None
        if try_vlib:
            # get presented version of lib
            lib_version = 0
            force_version = lib_cfg.get_force_version()
            if force_version is not None:
                lib_version = force_version
            log_libmgr.info("vlib: version=%d, fake=%s", lib_version, fake)
            # open vlib
            vlib = self.vlib_mgr.open_lib_name(
                base_name, version=lib_version, fake=fake, lib_cfg=lib_cfg
            )
            if vlib:
                addr = vlib.get_addr()
                log_libmgr.info("got vlib: @%06x", addr)

        # try amiga lib
        if try_alib and addr == 0:
            addr = self.alib_mgr.open_lib(full_name, cwd_lock, run_sp, progdir_lock)
            if addr > 0:
                log_libmgr.info("got alib: @%06x", addr)

        # got a lib? check version
        if addr > 0:
            save_addr = addr
            if version > 0:
                addr = self._check_version(full_name, addr, version)
            # lib is too old: close again
            if addr == 0:
                if vlib:
                    self.vlib_mgr.close_lib(vlib)
                else:
                    self.alib_mgr.close_lib(save_addr, run_sp=run_sp)

        # result lib base
        return addr

    def _map_mode(self, mode):
        if mode == LibCfg.CREATE_MODE_AUTO:
            try_vlib = True
            try_alib = True
            fake = False
        elif mode == LibCfg.CREATE_MODE_VAMOS:
            try_vlib = True
            try_alib = False
            fake = False
        elif mode == LibCfg.CREATE_MODE_AMIGA:
            try_vlib = False
            try_alib = True
            fake = False
        elif mode == LibCfg.CREATE_MODE_FAKE:
            try_vlib = True
            try_alib = False
            fake = True
        else:
            raise ValueError("invalid lib mode: '%s'" % mode)
        return try_vlib, try_alib, fake

    def _check_version(self, name, addr, open_ver):
        # check version
        lib = Library(self.mem, addr)
        lib_ver = lib.version.val
        if lib_ver < open_ver:
            log_libmgr.warning(
                "lib '%s' has too low version: %d < %d", name, lib_ver, open_ver
            )
            return 0
        else:
            log_libmgr.info(
                "lib '%s' version %d ok for open version %d", name, lib_ver, open_ver
            )
            return addr
