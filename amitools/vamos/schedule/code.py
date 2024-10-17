from amitools.vamos.machine import REG_D0


class Code:
    """an interface for managing native code associated with a task"""

    def __init__(self, start_pc, start_regs=None, return_regs=None):
        self.start_pc = start_pc
        if not start_regs:
            start_regs = {}
        if not return_regs:
            return_regs = [REG_D0]
        self.start_regs = start_regs
        self.return_regs = return_regs
        self.mem_obj = None
        self.alloc = None

    def __repr__(self):
        return "Code(start_pc=%06x, start_regs=%r, return_regs=%r)" % (
            self.start_pc,
            self.start_regs,
            self.return_regs,
        )

    def free(self):
        if not self.mem_obj:
            return
        self.alloc.free_memory(self.mem_obj)
        self.alloc = None
        self.mem_obj = None

    def get_start_pc(self):
        return self.start_pc

    def get_start_regs(self):
        return self.start_regs

    def get_return_regs(self):
        return self.return_regs

    @classmethod
    def alloc(
        cls, alloc, size, name=None, start_regs=None, return_regs=None, start_offset=0
    ):
        if name is None:
            name = "Code(%db)" % size
        mem_obj = alloc.alloc_memory(size, label=name)
        start_pc = mem_obj.addr + start_offset
        code = cls(start_pc, start_regs, return_regs)
        code.mem_obj = mem_obj
        code.alloc = alloc
        return code
