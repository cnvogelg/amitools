
from MemoryStruct import MemoryStruct
from MemoryLayout import InvalidMemoryAccessError
from CPU import *

class AmigaLibrary(MemoryStruct):
  
  op_rts = 0x4e75
  
  def __init__(self, name, version, bias, num_vectors, struct, context):
    self.name = name
    self.version = version
    self.bias = bias
    self.num_vectors = num_vectors
    self.struct = struct
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
  
  def __str__(self):
    return "[AmigaLib:%s V%d bias=%d num_vectors=%d pos_size=%d neg_size=%d [%06x ... %06x ... %06x]]" % \
      (self.name, self.version, self.bias, self.num_vectors, self.pos_size, self.neg_size, self.begin_addr, self.base_addr, self.end_addr)
  
  def set_addr(self, addr):
    self.base_addr = addr
    self.begin_addr = addr - self.neg_size
    self.pos_size = self.struct.get_size()
    self.end_addr = addr + self.pos_size
    MemoryStruct.__init__(self, self.name, addr, self.struct)    

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
    return ((addr >= self.begin_addr) and (addr < self.end_addr))
    
  def read_mem(self, width, addr):
    # pos range -> redirect to struct
    if addr >= self.addr:
      return MemoryStruct.read_mem(self, width, addr)
    # trap lib call and return RTS opcode
    elif(width == 1):
      self.call_vector(addr)
      return self.op_rts
    # invalid access to neg area
    else:
      raise InvalidMemoryAccessError(width, addr)

  def write_mem(self, width, addr, val):
    # pos range -> redirect to struct
    if addr >= self.addr:
      return MemoryStruct.write_mem(self, width, addr, val)
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