from amitools.vamos.MemoryBlock import MemoryBlock

class MemoryStruct(MemoryBlock):
  def __init__(self, name, addr, struct):
    MemoryBlock.__init__(self, name, addr, struct.get_size())
    self._struct = struct
  
  def read_mem(self, width, addr):
    delta = addr - self.addr
    name,off = self.struct.get_name_for_offset(delta, width)
    val = MemoryBlock.read_mem(self, width, addr)
    print "  R(%d): Struct +%d %s: %s+%d -> %d" % (2**width, delta, self.name, name, off, val)
    return val

  def write_mem(self, width, addr, val):
    delta = addr - self.addr
    name,off = self.struct.get_name_for_offset(delta, width)
    print "  W(%d): Struct +%d %s: %s+%d <- %d" % (2**width, delta, self.name, name, off, val)
    return MemoryBlock.write_mem(self, width, addr)  