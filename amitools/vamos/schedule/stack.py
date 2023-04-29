class Stack(object):
    """describe a stack in memory"""

    def __init__(self, lower, upper, initial_sp=None):
        self.lower = lower
        self.upper = upper
        self.size = upper - lower
        if initial_sp:
            self.initial_sp = initial_sp
        else:
            # reserve last long for size by default
            self.initial_sp = upper - 8
        # for alloc'ed stack
        self.mem_obj = None
        self.alloc = None

    def __repr__(self):
        return "Stack(lower=%06x, upper=%06x, initial_sp=%06x)" % (
            self.lower,
            self.upper,
            self.initial_sp,
        )

    def get_upper(self):
        return self.upper

    def get_lower(self):
        return self.lower

    def get_size(self):
        return self.size

    def get_initial_sp(self):
        return self.initial_sp

    def free(self):
        if not self.mem_obj:
            raise RuntimeError("free() without alloc()")
        self.alloc.free_memory(self.mem_obj)
        self.alloc = None
        self.mem_obj = None

    @classmethod
    def alloc(cls, alloc, size, name=None):
        if name is None:
            name = "Stack(%db)" % size
        mem_obj = alloc.alloc_memory(size, label=name)
        lower = mem_obj.addr
        upper = lower + size
        stack = Stack(lower, upper)
        stack.mem_obj = mem_obj
        stack.alloc = alloc
        # store size in top of stack
        mem = alloc.get_mem()
        mem.w32(upper - 4, size)
        return stack
