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
        return "{}(value={}, addr={})".format(
            self.__class__.__name__, self.get(), self._addr
        )

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
        return self._cpu.rs_reg(self._reg)

    def _write_reg(self, val):
        self._cpu.ws_reg(self._reg, val)

    def _read_mem(self):
        return self._mem.reads(self._mem_width, self._addr)

    def _write_mem(self, val):
        self._mem.writes(self._mem_width, self._addr, val)


class UnsignedType(ScalarType):
    _signed = False

    def _read_reg(self):
        return self._cpu.r_reg(self._reg)

    def _write_reg(self, val):
        self._cpu.w_reg(self._reg, val)

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
