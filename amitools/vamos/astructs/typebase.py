class TypeBase:
    """Base class for all Amiga types

    Namely scalars, pointers, arrays, and structs. Some type instances
    (pointer, scalars) can be read from/written to CPU regs. All type
    instances can be bound to a memory location and read from/written to
    there.
    """

    # type parameters (will be overwritten in derived classes)
    _byte_size = None

    @classmethod
    def get_byte_size(cls):
        """return the memory footprint in bytes"""
        return cls._byte_size

    @classmethod
    def get_size(cls):
        """return the memory footprint in bytes"""
        return cls._byte_size

    @classmethod
    def get_signature(cls):
        """return the type signature"""
        return cls.__name__

    @classmethod
    def get_alias_type(cls):
        """return the type alias (amiga class instead of struct) or the struct"""
        return cls

    # --- instance ---

    def __init__(
        self,
        mem=None,
        addr=None,
        cpu=None,
        reg=None,
        offset=0,
        base_offset=0,
        alloc=None,
        mem_obj=None,
        **kwargs,
    ):
        """create instance of a type.

        If you pass mem and addr than the type is bound to a memory location.
        If you pass a register then the value is bound to the CPU register.
        """
        self._mem = mem
        self._addr = addr
        self._reg = reg
        self._cpu = cpu
        self._offset = offset
        self._base_offset = base_offset
        # optional allocation
        self._mem_obj = mem_obj
        self._alloc = alloc
        # both addr and reg are not allowed
        assert not (reg and addr)
        if reg:
            assert cpu

    def __eq__(self, other):
        if type(other) is int:
            return self._addr == other
        elif isinstance(other, self.__class__):
            return self._addr == other._addr
        else:
            return NotImplemented

    def get_addr(self):
        """if type is bound to memory then return address otherwise None."""
        return self._addr

    def get_reg(self):
        """if type is bound to CPU register then return register otherwise None."""

    def get_mem(self):
        """return associated mem object."""
        return self._mem

    def get_cpu(self):
        """if type is bound to CPU register return CPU instance otherwise None."""
        return self._cpu

    def get_offset(self):
        """if type is embedded in a structure then return its byte offset"""
        return self._offset

    def get_base_offset(self):
        """if type is embedded in a sub structure then return its global offset"""
        return self._base_offset

    def __getattr__(self, key):
        if key == "addr":
            return self._addr
        elif key == "mem":
            return self._mem
        elif key == "cpu":
            return self._cpu
        elif key == "reg":
            return self._reg
        elif key == "offset":
            return self._offset
        elif key == "base_offset":
            return self._base_offset
        else:
            raise AttributeError("Invalid get key '{}' in {}".format(key, repr(self)))

    def __setattr__(self, key, val):
        # check for invalid keys
        if key in ("val", "aptr", "bptr", "ref"):
            raise AttributeError("Invalid set key '{}' in {}".format(key, repr(self)))
        super().__setattr__(key, val)

    # allocation

    @classmethod
    def alloc(cls, alloc, *alloc_args, tag=None, **kwargs):
        if not tag:
            tag = cls.get_signature()
        mem_obj = cls._alloc(alloc, tag, *alloc_args)
        if not mem_obj:
            return None
        # create instance of this or alias type
        cls_type = cls.get_alias_type()
        return cls_type(
            mem=alloc.get_mem(),
            addr=mem_obj.addr,
            alloc=alloc,
            mem_obj=mem_obj,
            **kwargs,
        )

    @classmethod
    def _alloc(cls, alloc, tag):
        return alloc.alloc_memory(cls._byte_size, label=tag)

    @classmethod
    def _free(cls, alloc, mem_obj):
        alloc.free_memory(mem_obj)

    def free(self):
        assert self._alloc and self._mem_obj
        self._free(self._alloc, self._mem_obj)
        self._alloc = None
        self._mem_obj = None
