import struct


class MockMemory(object):
    """fake the machine's memory API and work on a large bytearray"""

    def __init__(self, size_kib=16, fill=0):
        self.size_kib = size_kib
        self.size_bytes = size_kib * 1024
        self.data = bytearray(self.size_bytes)
        if fill != 0:
            for i in range(self.size_bytes):
                self.data[i] = fill

    def get_ram_size_kib(self):
        return self.size_kib

    def get_ram_size_bytes(self):
        return self.size_bytes

    def reserve_special_range(self, num_pages=1):
        raise NotImplementedError()

    def set_special_range_read_func(self, page_addr, width, func):
        raise NotImplementedError()

    def set_special_range_write_func(self, page_addr, width, func):
        raise NotImplementedError()

    def set_special_range_read_funcs(
        self, addr, num_pages=1, r8=None, r16=None, r32=None
    ):
        raise NotImplementedError()

    def set_special_range_write_funcs(
        self, addr, num_pages=1, w8=None, w16=None, w32=None
    ):
        raise NotImplementedError()

    def set_trace_mode(self, on):
        raise NotImplementedError()

    def set_trace_func(self, func):
        raise NotImplementedError()

    def set_invalid_func(self, func):
        raise NotImplementedError()

    # memory access (full range including special)
    def r8(self, addr):
        return self.data[addr]

    def r16(self, addr):
        return struct.unpack_from(">H", self.data, addr)[0]

    def r32(self, addr):
        return struct.unpack_from(">I", self.data, addr)[0]

    def w8(self, addr, value):
        self.data[addr] = value

    def w16(self, addr, value):
        struct.pack_into(">H", self.data, addr, value)

    def w32(self, addr, value):
        struct.pack_into(">I", self.data, addr, value)

    # signed memory access (full range including special)
    def r8s(self, addr):
        return struct.unpack_from(">b", self.data, addr)[0]

    def r16s(self, addr):
        return struct.unpack_from(">h", self.data, addr)[0]

    def r32s(self, addr):
        return struct.unpack_from(">i", self.data, addr)[0]

    def w8s(self, addr, value):
        struct.pack_into(">b", self.data, addr, value)

    def w16s(self, addr, value):
        struct.pack_into(">h", self.data, addr, value)

    def w32s(self, addr, value):
        struct.pack_into(">i", self.data, addr, value)

    # arbitrary width (full range including special)
    def read(self, width, addr):
        if width == 0:
            return self.r8(addr)
        elif width == 1:
            return self.r16(addr)
        elif width == 2:
            return self.r32(addr)
        else:
            raise ValueError("invalid width: %s" % width)

    def write(self, width, addr, value):
        if width == 0:
            self.w8(addr, value)
        elif width == 1:
            self.w16(addr, value)
        elif width == 2:
            self.w32(addr, value)
        else:
            raise ValueError("invalid width: %s" % width)

    # signed arbitrary width (full range including special)
    def reads(self, width, addr):
        if width == 0:
            return self.r8s(addr)
        elif width == 1:
            return self.r16s(addr)
        elif width == 2:
            return self.r32s(addr)
        else:
            raise ValueError("invalid width: %s" % width)

    def writes(self, width, addr, value):
        if width == 0:
            self.w8s(addr, value)
        elif width == 1:
            self.w16s(addr, value)
        elif width == 2:
            self.w32s(addr, value)
        else:
            raise ValueError("invalid width: %s" % width)

    # block access via str/bytearray (only RAM!)
    def r_block(self, addr, size):
        if (addr + size) > self.size_bytes:
            raise ValueError("block too large")
        return bytearray(self.data[addr : addr + size])

    def w_block(self, addr, data):
        size = len(data)
        if (addr + size) > self.size_bytes:
            raise ValueError("block too large")
        self.data[addr : addr + size] = data

    def clear_block(self, addr, size, value):
        if (addr + size) > self.size_bytes:
            raise ValueError("block too large")
        self.data[addr : addr + size] = bytes([value] * size)

    def copy_block(self, from_addr, to_addr, size):
        if (from_addr + size) > self.size_bytes or (to_addr + size) > self.size_bytes:
            raise ValueError("block too large")
        data = self.data[from_addr : from_addr + size]
        self.data[to_addr : to_addr + size] = data

    # helpers for c-strings (only RAM)
    def r_cstr(self, addr):
        if addr > self.size_bytes:
            raise ValueError("no RAM")
        res = []
        while True:
            ch = self.data[addr]
            if ch == 0:
                break
            res.append(ch)
            addr += 1
        return bytes(res).decode("latin-1")

    def w_cstr(self, addr, string):
        if addr > self.size_bytes:
            raise ValueError("no RAM")
        data = string.encode("latin-1") + b"\0"
        size = len(data)
        self.data[addr : addr + size] = data

    # helpers for bcpl-strings (only RAM)
    def r_bstr(self, addr):
        if addr > self.size_bytes:
            raise ValueError("no RAM")
        size = self.data[addr]
        addr += 1
        data = self.data[addr : addr + size]
        return data.decode("latin-1")

    def w_bstr(self, addr, string):
        if addr > self.size_bytes:
            raise ValueError("no RAM")
        size = len(string)
        if size > 255:
            raise ValueError("string too long")
        self.data[addr] = size
        addr += 1
        self.data[addr : addr + size] = string.encode("latin-1")
