import struct


class MemoryCache(object):
    """copy a region of emulator memory to a python bytearray
    to work on it faster"""

    def __init__(self, start_addr, size_bytes):
        """create cache of given byte size representing addr range"""
        self.start_addr = start_addr
        self.size_bytes = size_bytes
        self.end_addr = start_addr + size_bytes
        self.data = bytearray(self.size_bytes)

    def read_cache(self, mem):
        """read cache memory from emulator memory"""
        self.data = mem.r_block(self.start_addr, self.size_bytes)
        assert type(self.data) is bytearray

    def write_cache(self, mem):
        """write cache memory back to emulator memory"""
        mem.w_block(self.start_addr, self.data)

    def _check(self, addr, size=1):
        if addr < self.start_addr:
            raise ValueError("address %06x too small (%06x)" % (addr, self.start_addr))
        if (addr + size) > self.end_addr:
            raise ValueError("address %06x too large (%06x)" % (addr, self.end_addr))

    # memory access (full range including special)
    def r8(self, addr):
        self._check(addr)
        addr -= self.start_addr
        return self.data[addr]

    def r16(self, addr):
        self._check(addr, 2)
        addr -= self.start_addr
        return struct.unpack_from(">H", self.data, addr)[0]

    def r32(self, addr):
        self._check(addr, 4)
        addr -= self.start_addr
        return struct.unpack_from(">I", self.data, addr)[0]

    def w8(self, addr, value):
        self._check(addr)
        addr -= self.start_addr
        self.data[addr] = value

    def w16(self, addr, value):
        self._check(addr, 2)
        addr -= self.start_addr
        struct.pack_into(">H", self.data, addr, value)

    def w32(self, addr, value):
        self._check(addr, 4)
        addr -= self.start_addr
        struct.pack_into(">I", self.data, addr, value)

    # signed memory access (full range including special)
    def r8s(self, addr):
        self._check(addr)
        addr -= self.start_addr
        return struct.unpack_from(">b", self.data, addr)[0]

    def r16s(self, addr):
        self._check(addr, 2)
        addr -= self.start_addr
        return struct.unpack_from(">h", self.data, addr)[0]

    def r32s(self, addr):
        self._check(addr, 4)
        addr -= self.start_addr
        return struct.unpack_from(">i", self.data, addr)[0]

    def w8s(self, addr, value):
        self._check(addr)
        addr -= self.start_addr
        struct.pack_into(">b", self.data, addr, value)

    def w16s(self, addr, value):
        self._check(addr, 2)
        addr -= self.start_addr
        struct.pack_into(">h", self.data, addr, value)

    def w32s(self, addr, value):
        self._check(addr, 4)
        addr -= self.start_addr
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
        self._check(addr, size)
        addr -= self.start_addr
        return bytearray(self.data[addr : addr + size])

    def w_block(self, addr, data):
        size = len(data)
        self._check(addr, size)
        addr -= self.start_addr
        self.data[addr : addr + size] = data

    def clear_block(self, addr, size, value):
        self._check(addr, size)
        addr -= self.start_addr
        self.data[addr : addr + size] = bytes([value] * size)

    def copy_block(self, from_addr, to_addr, size):
        self._check(from_addr, size)
        self._check(to_addr, size)
        from_addr -= self.start_addr
        to_addr -= self.start_addr
        data = self.data[from_addr : from_addr + size]
        self.data[to_addr : to_addr + size] = data

    # helpers for c-strings (only RAM)
    def r_cstr(self, addr):
        self._check(addr)
        addr -= self.start_addr
        res = []
        while True:
            ch = self.data[addr]
            if ch == 0:
                break
            res.append(ch)
            addr += 1
        return bytes(res).decode("latin-1")

    def w_cstr(self, addr, string):
        data = string.encode("latin1") + b"\0"
        size = len(data)
        self._check(addr, size)
        addr -= self.start_addr
        self.data[addr : addr + size] = data

    # helpers for bcpl-strings (only RAM)
    def r_bstr(self, addr):
        self._check(addr)
        addr -= self.start_addr
        size = self.data[addr]
        addr += 1
        data = self.data[addr : addr + size]
        return data.decode("latin-1")

    def w_bstr(self, addr, string):
        data = string.encode("latin-1")
        size = len(data)
        self._check(addr, size)
        addr -= self.start_addr
        self.data[addr] = size
        addr += 1
        self.data[addr : addr + size] = data
