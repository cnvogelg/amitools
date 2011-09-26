from MemoryRange import MemoryRange
import ctypes
import struct

class MemoryBlock(MemoryRange):
  
  def __init__(self, name, addr, size):
    MemoryRange.__init__(self, name, addr, size)
    self.buffer = ctypes.create_string_buffer(size)
    self.rfunc = (self.r8, self.r16, self.r32)
    self.wfunc = (self.w8, self.w16, self.w32)
    
  # 'memory access'
  def r8(self, addr):
    return struct.unpack_from("B",self.buffer,offset=addr - self.addr)[0]

  def r16(self, addr):
    return struct.unpack_from(">H",self.buffer,offset=addr - self.addr)[0]

  def r32(self, addr):
    return struct.unpack_from(">I",self.buffer,offset=addr - self.addr)[0]

  def w8(self, addr, v):
    struct.pack_into("B",self.buffer,addr-self.addr,v)

  def w16(self, addr, v):
    struct.pack_into(">H",self.buffer,addr-self.addr,v)

  def w32(self, addr, v):
    struct.pack_into(">I",self.buffer,addr-self.addr,v)
  
  def read_mem(self, width, addr):
    return self.rfunc[width](addr)

  def write_mem(self, width, addr, val):
    self.wfunc[width](addr, val)
    
  def write_data(self, addr, data):
    off = addr - self.addr
    for d in data:
      self.buffer[off] = d
      off += 1
  
  def read_data(self, addr, size):
    off = addr - self.addr
    buf = " " * size
    for i in xrange(size):
      buf[i] = self.buffer[off]
      off += 1
    return buf

  def read_cstring(self, addr):
    off = addr - self.addr
    res = ""
    while self.buffer[off] != '\0':
      res += self.buffer[off]
      off += 1
    return res

    
    