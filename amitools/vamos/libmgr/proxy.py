from amitools.vamos.log import log_libmgr
from amitools.vamos.libcore import LibProxyGen, LibCtx
from amitools.vamos.error import VamosInternalError


class LibProxyManager:
    def __init__(self, lib_mgr):
        self.lib_mgr = lib_mgr
        self.proxy_cache = {}
        self.proxy_gen = LibProxyGen()
        # on demand convenience proxies
        self.exec_lib_proxy = None
        self.dos_lib_proxy = None

    def get_exec_lib_proxy(self):
        # auto open exec
        exec = self.exec_lib_proxy
        if not exec:
            exec = self.open_lib_proxy("exec.library")
            self.exec_lib_proxy = exec
        return exec

    def get_dos_lib_proxy(self):
        # auto open dos
        dos = self.dos_lib_proxy
        if not dos:
            dos = self.open_lib_proxy("dos.library")
            self.dos_lib_proxy = dos
        return dos

    def shutdown(self):
        # auto close exec
        exec = self.exec_lib_proxy
        if exec:
            self.close_lib_proxy(exec)
        # auto close dos
        dos = self.dos_lib_proxy
        if dos:
            self.close_lib_proxy(dos)

    def open_lib_proxy(self, full_name, version=0, run_sp=None):
        """Try to open library (vlib or alib) and return a python call proxy"""
        # try to open lib
        base_addr = self.lib_mgr.open_lib(full_name, version=version, run_sp=run_sp)
        if base_addr == 0:
            log_libmgr.warning("proxy: open_lib '%s' failed!", full_name)
            return None
        # is a vlib?
        vlib = self.lib_mgr.get_vlib_by_addr(base_addr)
        if vlib:
            return self._setup_stub_proxy(vlib, base_addr)
        else:
            # is an alib?
            ainfo = self.lib_mgr.get_alib_info_by_addr(base_addr)
            if ainfo:
                fd = ainfo.get_lib_fd()
                name = ainfo.get_name()
                # if an fd is available then we could create a proxy
                if fd:
                    return self._setup_libcall_proxy(name, fd, base_addr, run_sp)
                else:
                    log_libmgr.warning("proxy: no FD for '%s'", full_name)
                    return None
            else:
                raise VamosInternalError("Neither vlib nor alib?!")

    def close_lib_proxy(self, proxy, run_sp=None):
        """Close the library assoicated with proxy and invalidate it."""
        base_addr = proxy.base_addr
        self.lib_mgr.close_lib(base_addr, run_sp=run_sp)
        proxy.ctx = None
        proxy.base_addr = None

    def _setup_stub_proxy(self, vlib, base_addr):
        name = vlib.info.name
        type_name = self._get_proxy_type_name(name)
        # cached proxy?
        proxy_type = self.proxy_cache.get(type_name, None)
        if not proxy_type:
            log_libmgr.info("proxy: create stub type '%s'", type_name)
            # no, create it
            proxy_type = self.proxy_gen.gen_proxy_for_stub(
                type_name, vlib.fd, vlib.stub
            )
            self.proxy_cache[type_name] = proxy_type
        # create instance
        log_libmgr.info("proxy: create stub proxy %s@%08x", type_name, base_addr)
        return proxy_type(vlib.ctx, base_addr)

    def _setup_libcall_proxy(self, name, fd, base_addr, run_sp):
        type_name = self._get_proxy_type_name(name)
        # cached proxy?
        proxy_type = self.proxy_cache.get(type_name, None)
        if not proxy_type:
            log_libmgr.info("proxy: create libcall type '%s'", type_name)
            # no, create it
            proxy_type = self.proxy_gen.gen_proxy_for_libcall(type_name, fd)
            self.proxy_cache[type_name] = proxy_type
        # create instance
        ctx = LibCtx(self.lib_mgr.machine)
        log_libmgr.info("proxy: create libcall proxy %s@%08x", type_name, base_addr)
        return proxy_type(ctx, base_addr, run_sp=run_sp)

    def _get_proxy_type_name(self, lib_name):
        """Normalize library name and strip path and extension"""
        pos = lib_name.find(":")
        if pos != -1:
            lib_name = lib_name[pos:]
        pos = lib_name.find("/")
        if pos != -1:
            lib_name = lib_name[pos:]
        pos = lib_name.find(".")
        if pos != -1:
            lib_name = lib_name[:pos]
        return lib_name
