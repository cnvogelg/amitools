from .typebase import TypeBase


class VOID(TypeBase):
    """A VOID instance only holds the address where the void exists."""

    def __repr__(self):
        return "VOID(addr={})".format(self._addr)


class PointerType(TypeBase):
    _byte_size = 4
    _ref_type = None

    @classmethod
    def get_ref_type(cls):
        return cls._ref_type

    @classmethod
    def get_signature(cls):
        return "{}*".format(cls._ref_type.get_signature())

    def __init__(self, mem=None, addr=None, cpu=None, reg=None, **kwargs):
        """create pointer type with referenced object"""
        super(PointerType, self).__init__(mem, addr, cpu, reg, **kwargs)
        self._ref = None
        self._ref_addr = None

    def setup(self, val, alloc=None, free_refs=None):
        if val is None:
            self.set_ref(None)
        elif type(val) is int:
            self.set_ref_addr(val)
        elif isinstance(val, self._ref_type):
            self.set_ref(val)
        else:
            if alloc:
                ref = self.alloc_ref(alloc)
                free_refs.append(ref)
                ref.setup(val, alloc, free_refs)
            else:
                raise ValueError("No alloc:" + val)

    def alloc_ref(self, alloc, *alloc_args, tag=None, **kwargs):
        # make sure nothing is allocated yet
        assert self._ref is None
        new_ref = self._ref_type.alloc(alloc, tag=tag, *alloc_args)
        self.set_ref(new_ref)
        return self.get_ref()

    def free_ref(self):
        assert self._ref
        self._ref.free()
        self.set_ref(None)

    def get_ref(self):
        """return the referenced type instance"""
        ref_addr = self._read_pointer()
        if ref_addr != self._ref_addr:
            self._ref = self._create_ref_at(ref_addr)
            self._ref_addr = ref_addr
        return self._ref

    def set_ref(self, ref):
        """set a new type instance"""
        self._ref = ref
        if not ref:
            self._ref_addr = 0
        else:
            assert isinstance(ref, self._ref_type)
            self._ref_addr = ref.get_addr()
        self._write_pointer(self._ref_addr)

    def get_ref_addr(self):
        return self._read_pointer()

    def set_ref_addr(self, ref_addr):
        self._ref = None
        self._ref_addr = None
        self._write_pointer(ref_addr)

    def get(self):
        return self.get_ref_addr()

    def set(self, ref_addr):
        self.set_ref_addr(ref_addr)

    def _read_pointer(self):
        if self._addr is not None:
            store_addr = self._mem.r32(self._addr)
        else:
            store_addr = self._cpu.r_reg(self._reg)
        ref_addr = self._store_to_ref_addr(store_addr)
        return ref_addr

    def _write_pointer(self, ref_addr):
        store_addr = self._ref_to_store_addr(ref_addr)
        if self._addr is not None:
            self._mem.w32(self._addr, store_addr)
        else:
            self._cpu.w_reg(self._reg, store_addr)

    def __repr__(self):
        return "{}(ref={}, addr={})".format(
            self.__class__.__name__, self._ref, self._addr
        )

    def __str__(self):
        return str(self.get_ref())

    def __int__(self):
        return self.get_ref_addr()

    def _store_to_ref_addr(self, addr):
        return addr

    def _ref_to_store_addr(self, addr):
        return addr

    def _create_ref_at(self, ref_addr):
        # null pointer
        if ref_addr == 0:
            return None
        cls_type = self._ref_type.get_alias_type()
        return cls_type(mem=self._mem, addr=ref_addr)

    def __getattr__(self, key):
        if key == "aptr":
            return self.get_ref_addr()
        elif key == "ref":
            return self.get_ref()
        else:
            return super(PointerType, self).__getattr__(key)

    def __setattr__(self, key, val):
        if key == "aptr":
            self.set_ref_addr(val)
        elif key == "ref":
            self.set_ref(val)
        else:
            super(PointerType, self).__setattr__(key, val)


class BCPLPointerType(PointerType):
    @classmethod
    def get_signature(cls):
        return "{}#".format(cls._ref_type.get_signature())

    def _store_to_ref_addr(self, addr):
        return addr << 2

    def _ref_to_store_addr(self, addr):
        return addr >> 2

    def get_ref_baddr(self):
        return self.get_ref_addr() >> 2

    def set_ref_baddr(self, baddr):
        self.set_ref_addr(baddr << 2)

    def get(self):
        return self.get_ref_baddr()

    def set(self, val):
        self.set_ref_baddr(val)

    def __int__(self):
        return self.get_ref_baddr()

    def __getattr__(self, key):
        if key == "bptr":
            return self.get_ref_baddr()
        else:
            return super(BCPLPointerType, self).__getattr__(key)

    def __setattr__(self, key, val):
        if key == "bptr":
            self.set_ref_baddr(val)
        else:
            super(BCPLPointerType, self).__setattr__(key, val)


# pointer type cache
APTRTypes = {}


def APTR(ref_type):
    """create a new pointer type class the references the given type"""
    name = "APTR_" + ref_type.__name__
    if name in APTRTypes:
        return APTRTypes[name]
    else:
        new_type = type(name, (PointerType,), dict(_ref_type=ref_type))
        APTRTypes[name] = new_type
        return new_type


# pointer type cache
BPTRTypes = {}


def BPTR(ref_type):
    """create a new pointer type class the references the given type"""
    name = "BPTR_" + ref_type.__name__
    if name in BPTRTypes:
        return BPTRTypes[name]
    else:
        new_type = type(name, (BCPLPointerType,), dict(_ref_type=ref_type))
        BPTRTypes[name] = new_type
        return new_type


APTR_VOID = APTR(VOID)
BPTR_VOID = BPTR(VOID)
