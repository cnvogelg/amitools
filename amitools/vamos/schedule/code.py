from amitools.vamos.machine import REG_D0


class Code:
    """an interface for managing native code associated with a task"""

    def __init__(self, start_pc, start_sp=None, start_regs=None, return_regs=None):
        self.start_pc = start_pc
        self.start_sp = start_sp
        if not start_regs:
            start_regs = {}
        if not return_regs:
            return_regs = [REG_D0]
        self.start_regs = start_regs
        self.return_regs = return_regs

    def __repr__(self):
        return "Code(start_pc=%06x, start_sp=%06x, start_regs=%r, return_regs=%r)" % (
            self.start_pc,
            self.start_sp,
            self.start_regs,
            self.return_regs,
        )

    def get_start_pc(self):
        return self.start_pc

    def get_start_sp(self):
        return self.start_sp

    def get_start_regs(self):
        return self.start_regs

    def get_return_regs(self):
        return self.return_regs
