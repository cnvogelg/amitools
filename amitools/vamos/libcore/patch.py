from .jumptab import LibJumpTable


class LibPatcherMultiTrap(object):
    """patch in a stub by adding traps for each call"""

    def __init__(self, alloc, traps, stub):
        self.alloc = alloc
        self.traps = traps
        self.stub = stub
        self.tids = []
        self.mem_obj = None
        self.trap_base = None

    def patch_jump_table(self, base_addr):
        """patch the stub into the jump table for the lib at base_addr"""
        self._setup_trap_block()
        # build jump table and point jumps to trap block
        neg_size = self.stub.fd.get_neg_size()
        fd = self.stub.fd
        jt = LibJumpTable(self.alloc.mem, base_addr, neg_size, fd=fd, create=True)
        addr = self.trap_base
        for entry in jt:
            entry.set(addr)
            addr += 2

    def _setup_trap_block(self):
        name = "%s(Traps)" % self.stub.name
        func_table = self.stub.get_func_tab()
        size = len(func_table) * 2
        self.mem_obj = self.alloc.alloc_memory(size, label=name)
        addr = self.mem_obj.addr
        self.trap_base = addr
        mem = self.alloc.mem
        for func in func_table:
            # setup new patch
            tid = self.traps.setup(func, auto_rts=True)
            if tid < 0:
                raise RuntimeError("no more traps available!")
            # generate opcode
            op = 0xA000 | tid
            # write trap
            mem.w16(addr, op)
            # remember trap
            self.tids.append(tid)
            # next slot
            addr += 2

    def cleanup(self):
        """remove traps"""
        for tid in self.tids:
            self.traps.free(tid)
        self.tids = []
        # free trap block
        self.alloc.free_memory(self.mem_obj)
        self.mem_obj = None
