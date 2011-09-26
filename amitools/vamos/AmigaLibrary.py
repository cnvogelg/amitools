
from MemoryBlock import MemoryBlock
from MemoryLayout import InvalidMemoryAccessError
from CPU import *

class AmigaLibrary(MemoryBlock):
  
  op_rts = 0x4e75
  
  def __init__(self, name, version, bias, num_vectors, pos_size, context):
    self.name = name
    self.version = version
    self.bias = bias
    self.num_vectors = num_vectors
    self.pos_size = pos_size
    self.context = context
    # calc neg_size
    self.neg_size = bias + num_vectors * 6
    
    # setup vector table
    self.vectors = []
    for i in xrange(num_vectors):
      self.vectors.append(None)

    # keep mem and cpu
    self.cpu = self.context.get_cpu()
    self.mem = self.context.get_mem()
    
  def set_addr(self, addr):
    self.base_addr = addr
    self.begin_addr = addr - self.neg_size
    self.end_addr = addr + self.pos_size
    MemoryBlock.__init__(self, self.name, addr, self.pos_size)    

  def add_key(self, key, callee, name="none", param=None, ret=REG_D0):
    off = (-key - self.bias) / 6
    self.add_offset(off, callee, name=name, param=param, ret=ret)
    
  def add_offset(self, off, callee, name="none", param=None, ret=REG_D0):
    self.vectors[off] = {
      "callee" : callee,
      "name" : name,
      "param" : param,
      "ret" : ret
    }

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
    off = (self.base_addr - self.bias - addr) / 6
    key = (addr - self.base_addr)
    vector = self.vectors[off]
    if vector != None:
      callee = vector['callee']
      print "  [%s] %s" % (self.name, vector['name'])
      callee()
    else:
      self.default_call(off,key)
    
  def default_call(self, off, key):
    print "  [%s] ignore call: off=%d key=%d" % (self.name,off,key) 
    self.cpu.w_reg(REG_D0, 0)