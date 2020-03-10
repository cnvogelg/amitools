class LabelRange:
    def __init__(self, name, addr, size):
        self.name = name
        self.addr = addr
        self.size = size
        self.end = addr + size
        self.next = None
        self.prev = None

    def __str__(self):
        return "<@%06x +%06x %06x> [%s]" % (
            self.addr,
            self.size,
            self.addr + self.size,
            self.name,
        )

    def is_inside(self, addr):
        return (self.addr <= addr) and (addr < self.end)

    def does_intersect(self, addr, size):
        self_end = self.addr + self.size
        end = addr + size
        f1 = end >= self.addr
        f2 = self_end >= addr
        return f1 and f2
