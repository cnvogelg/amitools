from .typebase import TypeBase


class ScalarType(TypeBase):
    _signed = None
    _mem_width = None

    @classmethod
    def is_signed(cls):
        """is scalar type signed?"""
        return cls._signed

    @classmethod
    def get_mem_width(cls):
        """return width of type in 2**n bytes.

        Non scalar types will raise an error.
        See WIDTH_* constants.
        """
        return cls._mem_width

    def __init__(self, mem=None, addr=None, cpu=None, reg=None, **kwargs):
        super(ScalarType, self).__init__(mem, addr, cpu, reg, **kwargs)

    def set(self, val):
        if self._addr is not None:
            self._write_mem(val)
        else:
            self._write_reg(val)

    def get(self):
        if self._addr is not None:
            return self._read_mem()
        else:
            return self._read_reg()

    def setup(self, val, alloc=None, free_refs=None):
        self.set(val)

    def _read_reg(self):
        raise RuntimeError

    def _write_reg(self):
        raise RuntimeError

    def _read_mem(self):
        raise RuntimeError

    def _write_mem(self):
        raise RuntimeError

    def __repr__(self):
        if self._addr is not None:
            return "{}(value={}, addr={})".format(
                self.__class__.__name__, self.get(), self._addr
            )
        else:
            return "{}(value={}, reg={})".format(
                self.__class__.__name__, self.get(), self._reg
            )

    def __str__(self):
        w = self.get_mem_width()
        if w == 2:
            f = "%08x/%d"
            m = 0xFFFFFFFF
        elif w == 1:
            f = "%04x/%d"
            m = 0xFFFF
        else:
            f = "%02x/%d"
            m = 0xFF
        v = self.get()
        return f % (v & m, v)

    def __int__(self):
        return self.get()

    def __getattr__(self, key):
        if key == "val":
            return self.get()
        else:
            return super(ScalarType, self).__getattr__(key)

    def __setattr__(self, key, val):
        if key == "val":
            self.set(val)
        else:
            super(ScalarType, self).__setattr__(key, val)


class SignedType(ScalarType):
    _signed = True

    def _read_reg(self):
        if self._byte_size == 4:
            return self._cpu.r32s_reg(self._reg)
        elif self._byte_size == 2:
            return self._cpu.r16s_reg(self._reg)
        elif self._byte_size == 1:
            return self._cpu.r8s_reg(self._reg)

    def _write_reg(self, val):
        if self._byte_size == 4:
            self._cpu.w32s_reg(self._reg, val)
        elif self._byte_size == 2:
            self._cpu.w16s_reg(self._reg, val)
        elif self._byte_size == 1:
            self._cpu.w8s_reg(self._reg, val)

    def _read_mem(self):
        return self._mem.reads(self._mem_width, self._addr)

    def _write_mem(self, val):
        self._mem.writes(self._mem_width, self._addr, val)


class UnsignedType(ScalarType):
    _signed = False

    def _read_reg(self):
        if self._byte_size == 4:
            return self._cpu.r32_reg(self._reg)
        elif self._byte_size == 2:
            return self._cpu.r16_reg(self._reg)
        elif self._byte_size == 1:
            return self._cpu.r8_reg(self._reg)

    def _write_reg(self, val):
        if self._byte_size == 4:
            self._cpu.w32_reg(self._reg, val)
        elif self._byte_size == 2:
            self._cpu.w16_reg(self._reg, val)
        elif self._byte_size == 1:
            self._cpu.w8_reg(self._reg, val)

    def _read_mem(self):
        return self._mem.read(self._mem_width, self._addr)

    def _write_mem(self, val):
        self._mem.write(self._mem_width, self._addr, val)


class LONG(SignedType):
    _byte_size = 4
    _mem_width = 2


class ULONG(UnsignedType):
    _byte_size = 4
    _mem_width = 2


class WORD(SignedType):
    _byte_size = 2
    _mem_width = 1


class UWORD(UnsignedType):
    _byte_size = 2
    _mem_width = 1


class BYTE(SignedType):
    _byte_size = 1
    _mem_width = 0


class UBYTE(UnsignedType):
    _byte_size = 1
    _mem_width = 0
