from amitools.vamos.libcore.impl import LibImpl

class GadToolsLibrary(LibImpl):
    def setup_lib(self, ctx, base_addr):
        #log_dos.info("setup dos.library")
        self.alloc = ctx.alloc

    def close_lib(self, ctx, open_cnt):
        pass
