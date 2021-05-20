class VLib(object):
    """a vamos interal lib.

    A vamos internal lib has a stub, a impl and allocator and patcher
    """

    def __init__(
        self,
        library,
        info,
        struct,
        fd,
        impl,
        stub,
        ctx,
        patcher,
        profile=None,
        is_dev=False,
    ):
        self.library = library
        self.info = info
        self.struct = struct
        self.fd = fd
        self.impl = impl
        self.stub = stub
        self.ctx = ctx
        self.patcher = patcher
        self.profile = profile
        self.is_dev = is_dev
        self._setup()

    def get_library(self):
        return self.library

    def get_info(self):
        return self.info

    def get_struct(self):
        return self.struct

    def get_fd(self):
        return self.fd

    def get_impl(self):
        return self.impl

    def get_stub(self):
        return self.stub

    def get_ctx(self):
        return self.ctx

    def get_patcher(self):
        return self.patcher

    def get_profile(self):
        return self.profile

    def is_device(self):
        return self.is_dev

    def get_name(self):
        return self.info.get_name()

    def get_addr(self):
        return self.library.get_addr()

    def _setup(self):
        if self.impl:
            self.impl.setup_lib(self.ctx, self.get_addr())

    def free(self):
        # check open cnt
        oc = self.library.open_cnt.val
        if oc > 0:
            raise RuntimeError("vlib.free(): has open_cnt: %d" % oc)
        # call cleanup func in impl
        if self.impl:
            self.impl.finish_lib(self.ctx)
        # cleanup patcher
        self.patcher.cleanup()
        # free library memory
        self.library.free()
        # clear members but leave alone ctx and profile
        self.library = None
        self.stub = None
        self.impl = None
        self.patcher = None

    def open(self):
        lib = self.library
        lib.inc_open_cnt()
        # report open to impl
        if self.impl:
            self.impl.open_lib(self.ctx, lib.open_cnt.val)

    def close(self):
        lib = self.library
        lib.dec_open_cnt()
        oc = lib.open_cnt.val
        if oc < 0:
            raise ValueError("vlib.close(): open_cnt < 0: %d" % oc)
        # report close to impl
        if self.impl:
            self.impl.close_lib(self.ctx, lib.open_cnt.val)
