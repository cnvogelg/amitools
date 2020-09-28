from amitools.vamos.machine.opcodes import op_jmp


class NoJumpTableEntryError(ValueError):
    def __init__(self, addr):
        self.addr = addr

    def __repr__(self):
        return "NoJumpTableEntryError(addr=%06x)" % self.addr


class LibJumpTableEntry(object):
    def __init__(self, jt, idx):
        self.jt = jt
        self.idx = idx
        self.lvo = (idx + 1) * -6
        self.name = None
        if self.jt._fd:
            func = jt._fd.get_func_by_index(idx)
            if func:
                self.name = func.get_name()

    def __str__(self):
        return "#%03d  (%-04d)  %-20s  %06x" % (
            self.idx,
            self.lvo,
            self.name,
            self.get(),
        )

    def __int__(self):
        return self.get()

    def get(self):
        return self.jt._get_addr_by_index(self.idx)

    def set(self, addr):
        return self.jt._set_addr_by_index(self.idx, addr)


class LibJumpTableIter(object):
    def __init__(self, jt):
        self.jt = jt
        self.idx = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.idx >= self.jt._max_index:
            raise StopIteration
        idx = self.idx
        self.idx += 1
        return LibJumpTableEntry(self.jt, idx)


class LibJumpTable(object):
    """Query and edit the jump table of a library"""

    def __init__(self, mem, lib_base, neg_size, fd=None, create=False):
        self._mem = mem
        self._lib_base = lib_base
        self._neg_size = neg_size
        self._max_index = (neg_size - 6) // 6
        self._fd = fd
        self._create = create

    def _get_addr_by_index(self, idx):
        addr = self._lib_base - (idx + 1) * 6
        if self._mem.r16(addr) != op_jmp:
            raise NoJumpTableEntryError(addr)
        return self._mem.r32(addr + 2)

    def _set_addr_by_index(self, idx, jmp_addr):
        addr = self._lib_base - (idx + 1) * 6
        if self._create:
            self._mem.w16(addr, op_jmp)
        elif self._mem.r16(addr) != op_jmp:
            raise NoJumpTableEntryError(addr)
        self._mem.w32(addr + 2, jmp_addr)

    def __iter__(self):
        return LibJumpTableIter(self)

    def __getitem__(self, key):
        # allow to access by index (pos) or lvo (neg)
        if type(key) is not int:
            raise KeyError
        if key < 0:
            # lvoaccess
            if key % 6 != 0:
                raise IndexError
            # convert to index
            key = (-key - 6) // 6
        # index access
        if key > self._max_index:
            raise IndexError
        return self._get_addr_by_index(key)

    def __setitem__(self, key, val):
        # allow to access by index (pos) or lvo (neg)
        if type(key) is not int:
            raise KeyError
        if key < 0:
            # lvo access
            if key % 6 != 0:
                raise IndexError
            # convert to index
            key = (-key - 6) // 6
        # index access
        if key > self._max_index:
            raise IndexError
        return self._set_addr_by_index(key, val)

    def __getattr__(self, name):
        if self._fd:
            # access via func name in fd
            func = self._fd.get_func_by_name(name)
            if func:
                idx = func.get_index()
                return self._get_addr_by_index(idx)
        raise AttributeError

    def __setattr__(self, name, val):
        if name[0] == "_":
            # internal _member
            return object.__setattr__(self, name, val)
        elif self._fd:
            # set entry via func name
            func = self._fd.get_func_by_name(name)
            if func:
                idx = func.get_index()
                return self._set_addr_by_index(idx, val)
        raise AttributeError
