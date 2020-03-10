from .range import LabelRange


class LabelStruct(LabelRange):
    def __init__(self, name, addr, struct, size=0, offset=0):
        str_size = struct.get_size()
        if size < (str_size + offset):
            size = str_size + offset
        LabelRange.__init__(self, name, addr, size)
        self.struct = struct
        self.offset = offset
        self.struct_begin = addr + offset
        self.struct_end = self.struct_begin + str_size
        self.struct_size = str_size
