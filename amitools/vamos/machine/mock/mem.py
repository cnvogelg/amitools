import struct


class MockMemory(object):
    """fake the machine's memory API and work on a large bytearray"""

    def __init__(self, size_kib=16, fill=0, data=None, read_only=False, base_addr=0):
        self.size_kib = size_kib
        self.size_bytes = size_kib * 1024
        self.data = bytearray(self.size_bytes)
        self.read_only = read_only
        self.base_addr = base_addr
        if fill != 0:
            for i in range(self.size_bytes):
                self.data[i] = fill
        if data:
            self.data[:] = data

    def in_mem_addr(self, addr):
        addr -= self.base_addr
        return addr >= 0 and addr <= self.size_bytes

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
        return self.data[addr - self.base_addr]

    def r16(self, addr):
        return struct.unpack_from(">H", self.data, addr - self.base_addr)[0]

    def r32(self, addr):
        return struct.unpack_from(">I", self.data, addr - self.base_addr)[0]

    def w8(self, addr, value):
        if self.read_only:
            raise ValueError(f"write to ROM @{addr:08x}")
        self.data[addr - self.base_addr] = value

    def w16(self, addr, value):
        if self.read_only:
            raise ValueError(f"write to ROM @{addr:08x}")
        struct.pack_into(">H", self.data, addr - self.base_addr, value)

    def w32(self, addr, value):
        if self.read_only:
            raise ValueError(f"write to ROM @{addr:08x}")
        struct.pack_into(">I", self.data, addr - self.base_addr, value)

    # signed memory access (full range including special)
    def r8s(self, addr):
        return struct.unpack_from(">b", self.data, addr - self.base_addr)[0]

    def r16s(self, addr):
        return struct.unpack_from(">h", self.data, addr - self.base_addr)[0]

    def r32s(self, addr):
        return struct.unpack_from(">i", self.data, addr - self.base_addr)[0]

    def w8s(self, addr, value):
        if self.read_only:
            raise ValueError(f"write to ROM @{addr:08x}")
        struct.pack_into(">b", self.data, addr - self.base_addr, value)

    def w16s(self, addr, value):
        if self.read_only:
            raise ValueError(f"write to ROM @{addr:08x}")
        struct.pack_into(">h", self.data, addr - self.base_addr, value)

    def w32s(self, addr, value):
        if self.read_only:
            raise ValueError(f"write to ROM @{addr:08x}")
        struct.pack_into(">i", self.data, addr - self.base_addr, value)

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
        addr -= self.base_addr
        if (addr + size) > self.size_bytes:
            raise ValueError("block too large")
        return bytearray(self.data[addr : addr + size])

    def w_block(self, addr, data):
        if self.read_only:
            raise ValueError(f"write to ROM @{addr:08x}")
        addr -= self.base_addr
        size = len(data)
        if (addr + size) > self.size_bytes:
            raise ValueError("block too large")
        self.data[addr : addr + size] = data

    def clear_block(self, addr, size, value):
        if self.read_only:
            raise ValueError(f"write to ROM @{addr:08x}")
        addr -= self.base_addr
        if (addr + size) > self.size_bytes:
            raise ValueError("block too large")
        self.data[addr : addr + size] = bytes([value] * size)

    def copy_block(self, from_addr, to_addr, size):
        if self.read_only:
            raise ValueError(f"write to ROM @{from_addr:08x} @{to_addr:08x}")
        from_addr -= self.base_addr
        to_addr -= self.base_addr
        if (from_addr + size) > self.size_bytes or (to_addr + size) > self.size_bytes:
            raise ValueError("block too large")
        data = self.data[from_addr : from_addr + size]
        self.data[to_addr : to_addr + size] = data

    # helpers for c-strings (only RAM)
    def r_cstr(self, addr):
        addr -= self.base_addr
        if addr > self.size_bytes:
            raise ValueError(f"no RAM @{addr:08x}")
        res = []
        while True:
            ch = self.data[addr]
            if ch == 0:
                break
            res.append(ch)
            addr += 1
        return bytes(res).decode("latin-1")

    def w_cstr(self, addr, string):
        if self.read_only:
            raise ValueError(f"write to ROM @{addr:08x}")
        addr -= self.base_addr
        if addr > self.size_bytes:
            raise ValueError(f"no RAM @{addr:08x}")
        data = string.encode("latin-1") + b"\0"
        size = len(data)
        self.data[addr : addr + size] = data

    # helpers for bcpl-strings (only RAM)
    def r_bstr(self, addr):
        addr -= self.base_addr
        if addr > self.size_bytes:
            raise ValueError(f"no RAM @{addr:08x}")
        size = self.data[addr]
        addr += 1
        data = self.data[addr : addr + size]
        return data.decode("latin-1")

    def w_bstr(self, addr, string):
        if self.read_only:
            raise ValueError(f"write to ROM @{addr:08x}")
        addr -= self.base_addr
        if addr > self.size_bytes:
            raise ValueError(f"no RAM @{addr:08x}")
        size = len(string)
        if size > 255:
            raise ValueError("string too long")
        self.data[addr] = size
        addr += 1
        self.data[addr : addr + size] = string.encode("latin-1")


class MultiMockMemory(object):
    def __init__(self):
        self.mems = []
        self.first = None

    def add(self, mem):
        self.mems.append(mem)
        if not self.first:
            self.first = mem

    def get_ram_size_kib(self):
        return self.first.get_ram_size_kib()

    def get_ram_size_bytes(self):
        return self.first.get_ram_size_bytes()

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

    def _find_mem(self, addr):
        for mem in self.mems:
            if mem.in_mem_addr(addr):
                return mem
        raise ValueError(f"invalid addr {addr:08x}")

    # memory access (full range including special)
    def r8(self, addr):
        return self._find_mem(addr).r8(addr)

    def r16(self, addr):
        return self._find_mem(addr).r16(addr)

    def r32(self, addr):
        return self._find_mem(addr).r32(addr)

    def w8(self, addr, value):
        self._find_mem(addr).w8(addr, value)

    def w16(self, addr, value):
        self._find_mem(addr).w16(addr, value)

    def w32(self, addr, value):
        self._find_mem(addr).w32(addr, value)

    # signed memory access (full range including special)
    def r8s(self, addr):
        return self._find_mem(addr).r8s(addr)

    def r16s(self, addr):
        return self._find_mem(addr).r16s(addr)

    def r32s(self, addr):
        return self._find_mem(addr).r32s(addr)

    def w8s(self, addr, value):
        self._find_mem(addr).w8s(addr, value)

    def w16s(self, addr, value):
        self._find_mem(addr).w16s(addr, value)

    def w32s(self, addr, value):
        self._find_mem(addr).w32s(addr, value)

    # arbitrary width (full range including special)
    def read(self, width, addr):
        return self._find_mem(addr).read(width, addr)

    def write(self, width, addr, value):
        self._find_mem(addr).write(width, addr, value)

    # signed arbitrary width (full range including special)
    def reads(self, width, addr):
        return self._find_mem(addr).reads(width, addr)

    def writes(self, width, addr, value):
        self._find_mem(addr).writes(width, addr, value)

    # block access via str/bytearray (only RAM!)
    def r_block(self, addr, size):
        return self._find_mem(addr).r_block(addr, size)

    def w_block(self, addr, data):
        self._find_mem(addr).w_block(addr, data)

    def clear_block(self, addr, size, value):
        self._find_mem(addr).clear_block(addr, size, value)

    def copy_block(self, from_addr, to_addr, size):
        from_mem = self._find_mem(from_addr)
        to_mem = self._find_mem(to_addr)
        if from_mem == to_mem:
            from_mem.copy_block(from_addr, to_addr, size)
        else:
            data = from_mem.r_block(from_addr, size)
            to_mem.w_block(to_addr, data)

    # helpers for c-strings (only RAM)
    def r_cstr(self, addr):
        return self._find_mem(addr).r_cstr(addr)

    def w_cstr(self, addr, string):
        self._find_mem(addr).w_cstr(addr, string)

    # helpers for bcpl-strings (only RAM)
    def r_bstr(self, addr):
        return self._find_mem(addr).r_bstr(addr)

    def w_bstr(self, addr, string):
        self._find_mem(addr).w_bstr(addr, string)


class DummyMockMemory(object):
    def in_mem_addr(self, addr):
        return True

    # memory access (full range including special)
    def r8(self, addr):
        return 0

    def r16(self, addr):
        return 0

    def r32(self, addr):
        return 0

    def w8(self, addr, value):
        pass

    def w16(self, addr, value):
        pass

    def w32(self, addr, value):
        pass

    # signed memory access (full range including special)
    def r8s(self, addr):
        return 0

    def r16s(self, addr):
        return 0

    def r32s(self, addr):
        return 0

    def w8s(self, addr, value):
        pass

    def w16s(self, addr, value):
        pass

    def w32s(self, addr, value):
        pass

    # arbitrary width (full range including special)
    def read(self, width, addr):
        return 0

    def write(self, width, addr, value):
        pass

    # signed arbitrary width (full range including special)
    def reads(self, width, addr):
        return 0

    def writes(self, width, addr, value):
        pass

    # block access via str/bytearray (only RAM!)
    def r_block(self, addr, size):
        return bytearray(size)

    def w_block(self, addr, data):
        pass

    def clear_block(self, addr, size, value):
        pass

    def copy_block(self, from_addr, to_addr, size):
        pass

    # helpers for c-strings (only RAM)
    def r_cstr(self, addr):
        return ""

    def w_cstr(self, addr, string):
        pass

    # helpers for bcpl-strings (only RAM)
    def r_bstr(self, addr):
        return ""

    def w_bstr(self, addr, string):
        pass
