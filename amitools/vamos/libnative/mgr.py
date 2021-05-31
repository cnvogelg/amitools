from amitools.vamos.log import log_libmgr
from amitools.fd import read_lib_fd
from .loader import LibLoader
from .libfuncs import LibFuncs


class ALibInfo(object):
    def __init__(self, name, load_addr, seglist_baddr, lib_fd=None):
        self.name = name
        self.load_addr = load_addr
        self.seglist_baddr = seglist_baddr
        self.lib_fd = lib_fd
        self.base_addrs = {}

    def __str__(self):
        info = []
        for base_addr in self.base_addrs:
            num = self.base_addrs[base_addr]
            info.append("%06x: %d" % (base_addr, num))
        txt = ",".join(info)
        return "['%s':load=@%06x,seglist=%06x,addrs=%s]" % (
            self.name,
            self.load_addr,
            self.seglist_baddr,
            txt,
        )

    def get_name(self):
        return self.name

    def get_load_addr(self):
        return self.load_addr

    def get_seglist_baddr(self):
        return self.seglist_baddr

    def get_lib_fd(self):
        return self.lib_fd

    def add_base_addr(self, base_addr):
        if base_addr in self.base_addrs:
            self.base_addrs[base_addr] += 1
        else:
            self.base_addrs[base_addr] = 1

    def del_base_addr(self, base_addr):
        self.base_addrs[base_addr] -= 1
        if self.base_addrs[base_addr] == 0:
            del self.base_addrs[base_addr]

    def get_num_base_addrs(self):
        return len(self.base_addrs)

    def is_load_addr(self, addr):
        return addr == self.load_addr

    def is_base_addr(self, addr):
        for base_addr in self.base_addrs:
            if base_addr == addr:
                return True
        return False


class ALibManager(object):
    def __init__(self, machine, alloc, segloader):
        self.segloader = segloader
        self.loader = LibLoader(machine, alloc, segloader)
        self.funcs = LibFuncs(machine, alloc)
        self.mem = machine.get_mem()
        # state
        self.lib_infos = []

    def is_base_addr(self, addr):
        """check if a given addr is the lib base of a native lib
        return info if found or None
        """
        for info in self.lib_infos:
            if info.is_base_addr(addr):
                return info

    def is_load_addr(self, addr):
        """check if a given addr is the lib load addr
        return info if found or None
        """
        for info in self.lib_infos:
            if info.is_load_addr(addr):
                return info

    def get_lib_info_for_name(self, name):
        """return the (original loaded) base addr of lib given by name"""
        for info in self.lib_infos:
            if info.get_name() == name:
                return info

    def shutdown(self, run_sp=None):
        """return number of libs still left unexpunged"""
        return self.expunge_libs(run_sp)

    def expunge_libs(self, run_sp=None):
        """return number of libs still left unexpunged"""
        log_libmgr.info("[native] +expunge_libs")
        left_libs = 0
        for lib_info in self.lib_infos:
            log_libmgr.info("expunging: %s", lib_info)
            load_addr = lib_info.get_load_addr()
            seglist = self.expunge_lib(load_addr, run_sp)
            if not seglist:
                left_libs += 1
        log_libmgr.info("[native] -expunge_libs: %d left", left_libs)
        return left_libs

    def expunge_lib(self, load_addr, run_sp=None):
        log_libmgr.info("[native] +expunge_lib: load=@%06x", load_addr)
        info = self.is_load_addr(load_addr)
        if not info:
            raise ValueError("expunge_lib: invalid lib_load=%06x" % load_addr)
        seglist = self.funcs.rem_library(load_addr, self.segloader, run_sp)
        self._rem_info(load_addr, info, seglist, False)
        log_libmgr.info("[native] -expunge_lib: seglist=%06x, info=%s", seglist, info)
        return seglist

    def close_lib(self, base_addr, run_sp=None):
        log_libmgr.info("[native] +close_lib: base=@%06x", base_addr)
        info = self.is_base_addr(base_addr)
        if not info:
            raise ValueError("close_lib: invalid lib_base=%06x" % base_addr)
        seglist = self.funcs.close_library(base_addr, self.segloader, run_sp)
        self._rem_info(base_addr, info, seglist, True)
        log_libmgr.info("[native] -close_lib: seglist=%06x, info=%s", seglist, info)
        return seglist

    def open_lib(self, lib_name, cwd_lock=None, run_sp=None, progdir_lock=None):
        log_libmgr.info(
            "[native] +open_lib: lib_name='%s', cwd=%s, progdir=%s",
            lib_name,
            cwd_lock,
            progdir_lock,
        )
        # multict lib base name
        base_name = self.loader.get_lib_base_name(lib_name)
        # find library
        lib_info = self._find_info(base_name)
        log_libmgr.info("find: '%s' -> %s", base_name, lib_info)
        # not found... try to load it
        if not lib_info:
            log_libmgr.info("loading native lib: '%s'", lib_name)
            load_addr, seglist_baddr = self.loader.load_ami_lib(
                lib_name, cwd_lock, run_sp, progdir_lock
            )
            # even loading failed... abort
            if load_addr == 0:
                log_libmgr.info("[native] -open_lib: load failed!")
                return 0
            log_libmgr.info("loaded: @%06x  seglist: @%06x", load_addr, seglist_baddr)
            info = self.segloader.get_info(seglist_baddr)
            log_libmgr.info("loaded: %s", info)
            # try to load associated fd (if available)
            fd = read_lib_fd(base_name, add_std_calls=False)
            log_libmgr.info("loaded FD: '%s' -> %r", base_name, fd is not None)
            # store original load addr and name in info
            lib_info = self._add_info(base_name, load_addr, seglist_baddr, fd)
            loaded = True
        else:
            load_addr = lib_info.get_load_addr()
            loaded = False
        # got lib: open lib... may return new base!
        log_libmgr.debug("[native] call open lib: load_addr=%06x", load_addr)
        lib_base = self.funcs.open_library(load_addr, run_sp)
        # save base addr
        if lib_base > 0:
            lib_info.add_base_addr(lib_base)
        elif loaded:
            # remove lib info again
            self.lib_infos.remove(lib_info)
        log_libmgr.info(
            "[native] -open_lib: load_addr=@%06x, lib_base=@%06x, %s",
            load_addr,
            lib_base,
            lib_info,
        )
        # return base
        return lib_base

    def _find_info(self, base_name):
        for info in self.lib_infos:
            if info.get_name() == base_name:
                return info

    def _add_info(self, base_name, load_addr, seglist_baddr, fd):
        lib_info = ALibInfo(base_name, load_addr, seglist_baddr, fd)
        self.lib_infos.append(lib_info)
        return lib_info

    def _rem_info(self, addr, info, seglist_baddr, is_base):
        # remove base addr
        if info.is_base_addr(addr):
            info.del_base_addr(addr)
        # cleanup seglist
        if seglist_baddr > 0:
            assert info.get_num_base_addrs() == 0
            assert info.get_seglist_baddr() == seglist_baddr
            self.lib_infos.remove(info)
