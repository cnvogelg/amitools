from .struct import LabelStruct


class LabelLib(LabelStruct):

  def __init__(self, lib):
    name = lib.name
    addr = lib.addr_begin
    struct = lib.struct
    size = lib.mem_pos_size + lib.mem_neg_size
    lib_base = lib.addr_base
    LabelStruct.__init__(self, name, addr, struct,
                         size=size, offset=lib_base - addr)
    self.lib_base = lib_base
    self.lib = lib

  def __str__(self):
    return "%s base=%06x" % (LabelStruct.__str__(self), self.lib_base)
