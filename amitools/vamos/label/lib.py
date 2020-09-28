from .struct import LabelStruct


class LabelLib(LabelStruct):
    def __init__(self, name, addr, neg_size, pos_size, struct, fd=None):
        self.base_addr = addr
        self.pos_size = pos_size
        self.neg_size = neg_size
        self.fd = fd
        # setup a struct label
        size = pos_size + neg_size
        begin_addr = self.base_addr - neg_size
        LabelStruct.__init__(self, name, begin_addr, struct, size=size, offset=neg_size)

    def __str__(self):
        return "%s base=%06x -%d+%d" % (
            LabelStruct.__str__(self),
            self.base_addr,
            self.neg_size,
            self.pos_size,
        )
