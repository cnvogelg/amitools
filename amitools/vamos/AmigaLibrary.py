
from MemoryBlock import MemoryBlock
from MemoryLayout import InvalidMemoryAccessError

class AmigaLibrary(MemoryBlock):
  
  op_rts = 0x4e75
  
  def __init__(self, name, addr, num_vectors, pos_size):
    self.num_vectors = num_vectors
    self.begin_addr = addr - num_vectors * 6
    self.end_addr = addr + pos_size
    MemoryBlock.__init__(self, name, addr, pos_size)

  def is_inside(self, addr):
    return ((addr >= self.begin_addr) and (addr < self.addr))
    
  def read_mem(self, width, addr):
    # pos range -> redirect to memory
    if addr >= self.addr:
      return MemoryBlock.read_memory(self, width, addr)
    # trap lib call and return RTS opcode
    elif(width == 1):
      self.call_vector(addr)
      return self.op_rts
    # invalid access to neg area
    else:
      raise InvalidMemoryAccessError(width, addr)

  def write_mem(self, width, addr, val):
    # pos range -> redirect to memory
    if addr >= self.addr:
      return MemoryBlock.write_memory(self, width, addr, val)
    # writes to neg area are not allowed for now
    else:
      raise InvalidMemoryAccessError(width, addr)

  def call_vector(self, addr):
    off = addr - self.addr
    print "[%s] call: %d" % (self.name,off) 
