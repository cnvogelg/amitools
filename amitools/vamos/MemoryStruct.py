from amitools.vamos.MemoryBlock import MemoryBlock

class MemoryStruct(MemoryBlock):
  def __init__(self, name, addr, struct):
    MemoryBlock.__init__(self, name, addr, struct.get_size())
    self.struct = struct
  
  def read_mem(self, width, addr):
    delta = addr - self.addr
    name,off = self.struct.get_name_for_offset(delta, width)
    val = MemoryBlock.read_mem_int(self, width, addr)
    self.trace_read(width, addr, val, text="Struct %s+%d = %s+%d" % (self.name, delta, name, off))
    return val

  def write_mem(self, width, addr, val):
    delta = addr - self.addr
    name,off = self.struct.get_name_for_offset(delta, width)
    self.trace_write(width, addr, val, text="Struct %s+%d = %s+%d" % (self.name, delta, name, off))
    return MemoryBlock.write_mem_int(self, width, addr)  