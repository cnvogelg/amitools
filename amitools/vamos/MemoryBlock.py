from MemoryRange import MemoryRange
import ctypes
import struct
import logging

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
    val = self.rfunc[width](addr)
    self.trace_read(width, addr, val);
    return val

  def write_mem(self, width, addr, val):
    self.wfunc[width](addr, val)
    self.trace_write(width, addr, val);

  # for internal memory access without trace
  def read_mem_int(self, width, addr):
    return self.rfunc[width](addr)
  
  # for internal memory access without trace
  def write_mem_int(self, width, addr, val):
    self.wfunc[width](addr, val)
