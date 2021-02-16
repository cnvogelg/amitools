import logging


class TraceMemory:
    def __init__(self, mem, trace_mgr):
        """a front-end class to memory that does tracing"""
        self.mem = mem
        self.trace_mgr = trace_mgr

    def cleanup(self):
        self.mem.cleanup()

    def get_ram_size_kib(self):
        return self.mem.get_ram_size_kib()

    def get_ram_size_bytes(self):
        return self.mem.get_ram_size_bytes()

    def reserve_special_range(self, num_pages=1):
        return self.mem.reserve_special_range(num_pages)

    def set_special_range_read_func(self, page_addr, width, func):
        return self.mem.set_special_range_read_func(page_addr, width, func)

    def set_special_range_write_func(self, page_addr, width, func):
        return self.mem.set_special_range_write_func(page_addr, width, func)

    def set_special_range_read_funcs(
        self, addr, num_pages=1, r8=None, r16=None, r32=None
    ):
        return self.mem.set_special_range_read_funcs(addr, num_pages, r8, r16, r32)

    def set_special_range_write_funcs(
        self, addr, num_pages=1, w8=None, w16=None, w32=None
    ):
        return self.mem.set_special_range_write_funcs(addr, num_pages, w8, w16, w32)

    def set_trace_mode(self, on):
        return self.mem.set_trace_mode(on)

    def set_trace_func(self, func):
        return self.mem.set_trace_func(func)

    def set_invalid_func(self, func):
        return self.mem.set_invalid_func(func)

    # memory access
    def r32(self, addr):
        val = self.mem.r32(addr)
        self.trace_mgr.trace_int_mem("R", 2, addr, val)
        return val

    def r16(self, addr):
        val = self.mem.r16(addr)
        self.trace_mgr.trace_int_mem("R", 1, addr, val)
        return val

    def r8(self, addr):
        val = self.mem.r8(addr)
        self.trace_mgr.trace_int_mem("R", 0, addr, val)
        return val

    def w32(self, addr, val):
        self.mem.w32(addr, val)
        self.trace_mgr.trace_int_mem("W", 2, addr, val)

    def w16(self, addr, val):
        self.mem.w16(addr, val)
        self.trace_mgr.trace_int_mem("W", 1, addr, val)

    def w8(self, addr, val):
        self.mem.w8(addr, val)
        self.trace_mgr.trace_int_mem("W", 0, addr, val)

    # signed memory access
    def r32s(self, addr):
        val = self.mem.r32s(addr)
        self.trace_mgr.trace_int_mem("R", 2, addr, val)
        return val

    def r16s(self, addr):
        val = self.mem.r16s(addr)
        self.trace_mgr.trace_int_mem("R", 1, addr, val)
        return val

    def r8s(self, addr):
        val = self.mem.r8s(addr)
        self.trace_mgr.trace_int_mem("R", 0, addr, val)
        return val

    def w32s(self, addr, val):
        self.mem.w32s(addr, val)
        self.trace_mgr.trace_int_mem("W", 2, addr, val)

    def w16s(self, addr, val):
        self.mem.w16s(addr, val)
        self.trace_mgr.trace_int_mem("W", 1, addr, val)

    def w8s(self, addr, val):
        self.mem.w8s(addr, val)
        self.trace_mgr.trace_int_mem("W", 0, addr, val)

    # arbitrary width
    def read(self, width, addr):
        val = self.mem.read(width, addr)
        self.trace_mgr.trace_int_mem("R", width, addr, val)
        return val

    def write(self, width, addr, val):
        self.mem.write(width, addr, val)
        self.trace_mgr.trace_int_mem("W", width, addr, val)

    # signed arbitrary width
    def reads(self, width, addr):
        val = self.mem.reads(width, addr)
        self.trace_mgr.trace_int_mem("R", width, addr, val)
        return val

    def writes(self, width, addr, val):
        self.mem.writes(width, addr, val)
        self.trace_mgr.trace_int_mem("W", width, addr, val)

    # block access
    def w_block(self, addr, data):
        self.mem.w_block(addr, data)
        self.trace_mgr.trace_int_block("W", addr, len(data))

    def r_block(self, addr, size):
        data = self.mem.r_block(addr, size)
        self.trace_mgr.trace_int_block("R", addr, size)
        return data

    def clear_block(self, addr, size, value):
        self.mem.clear_block(addr, size, value)
        self.trace_mgr.trace_int_block("F", addr, size)

    def copy_block(self, src_addr, tgt_addr, size):
        self.mem.copy_block(src_addr, tgt_addr, size)
        self.trace_mgr.trace_int_block("C", tgt_addr, size)

    # string
    def r_cstr(self, addr):
        cstr = self.mem.r_cstr(addr)
        self.trace_mgr.trace_int_block(
            "R", addr, len(cstr), text="CSTR", addon="'%s'" % cstr
        )
        return cstr

    def w_cstr(self, addr, cstr):
        self.mem.w_cstr(addr, cstr)
        self.trace_mgr.trace_int_block(
            "W", addr, len(cstr), text="CSTR", addon="'%s'" % cstr
        )

    def r_bstr(self, addr):
        bstr = self.mem.r_bstr(addr)
        self.trace_mgr.trace_int_block(
            "R", addr, len(bstr), text="BSTR", addon="'%s'" % bstr
        )
        return bstr

    def w_bstr(self, addr, bstr):
        self.mem.w_bstr(addr, bstr)
        self.trace_mgr.trace_int_block(
            "W", addr, len(bstr), text="BSTR", addon="'%s'" % bstr
        )

    # bytes
    def r_cbytes(self, addr):
        cbytes = self.mem.r_cbytes(addr)
        self.trace_mgr.trace_int_block(
            "R", addr, len(cbytes), text="CBYT", addon="%r" % cbytes
        )
        return cbytes

    def w_cbytes(self, addr, cbytes):
        self.mem.w_cbytes(addr, cbytes)
        self.trace_mgr.trace_int_block(
            "W", addr, len(cbytes), text="CBYT", addon="%r" % cbytes
        )

    def r_bbytes(self, addr):
        bbytes = self.mem.r_bbytes(addr)
        self.trace_mgr.trace_int_block(
            "R", addr, len(bbytes), text="BBYT", addon="%r" % bbytes
        )
        return bbytes

    def w_bbytes(self, addr, bbytes):
        self.mem.w_bbytes(addr, bbytes)
        self.trace_mgr.trace_int_block(
            "W", addr, len(bbytes), text="BBYT", addon="%r" % bbytes
        )
