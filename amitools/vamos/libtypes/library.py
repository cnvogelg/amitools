from amitools.vamos.libstructs import LibraryStruct, NodeType
from amitools.vamos.label import LabelLib
from amitools.vamos.machine.opcodes import op_rts
from amitools.vamos.astructs import AmigaClassDef


class LibBase:
    def __init__(self, mem, addr, **kwargs):
        # if 'neg_size' is given then move base_addr of lib struct
        neg_size = kwargs.get("neg_size")
        if neg_size:
            addr += neg_size
        # now setup library struct
        super().__init__(mem, addr, **kwargs)

    @classmethod
    def _alloc(cls, alloc, tag, pos_size, neg_size, fd):
        if tag is None:
            tag = cls.get_signature()
        return alloc.alloc_lib(
            cls, pos_size=pos_size, neg_size=neg_size, fd=fd, label=tag
        )

    @classmethod
    def _free(cls, alloc, mem_obj):
        alloc.free_lib(mem_obj)

    @classmethod
    def alloc(cls, alloc, tag=None, pos_size=0, neg_size=0, fd=None, **kwargs):
        if pos_size == 0:
            pos_size = cls.get_byte_size()
        # round size
        neg_size = (neg_size + 3) & ~3
        # alloc lib
        return super().alloc(
            alloc,
            pos_size,
            neg_size,
            fd,
            tag=tag,
            pos_size=pos_size,
            neg_size=neg_size,
            **kwargs
        )


@AmigaClassDef
class Library(LibBase, LibraryStruct):
    def new_lib(self, version=0, revision=0, type=NodeType.NT_LIBRARY, pri=0, flags=0):
        """set all lib values but name, id_str, pos_size, neg_size."""
        node = self.node
        node.succ.aptr = 0
        node.pred.aptr = 0
        node.type.val = type
        node.pri.val = pri

        self.flags.val = flags
        self.pad.val = 0
        self.version.val = version
        self.revision.val = revision
        self.sum.val = 0
        self.open_cnt.val = 0

    def fill_funcs(self, opcode=None, param=None):
        """quickly fill the function table of a library with an opcode and param"""
        if opcode is None:
            opcode = op_rts
        neg_size = self.neg_size.val
        base_addr = self.get_addr()
        off = 6
        while off < neg_size:
            addr = base_addr - off
            self._mem.w16(addr, opcode)
            if param:
                self._mem.w32(addr + 2, param)
            off += 6

    def calc_sum(self):
        """calc the lib sum and return it"""
        neg_size = self.neg_size.val
        addr = self.get_addr() - neg_size
        lib_sum = 0
        while addr < self.get_addr():
            val = self._mem.r32(addr)
            lib_sum += val
            addr += 4
        lib_sum &= 0xFFFFFFFF
        return lib_sum

    def update_sum(self):
        """calc new lib sum and store it"""
        lib_sum = self.calc_sum()
        self.sum.val = lib_sum
        return lib_sum

    def check_sum(self):
        """calc and compare lib sum with stored value"""
        lib_sum = self.calc_sum()
        got_sum = self.sum.val
        return lib_sum == got_sum

    def inc_open_cnt(self):
        self.open_cnt.val += 1

    def dec_open_cnt(self):
        self.open_cnt.val -= 1
