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

  # for derived classes without trace
  def read_mem_int(self, width, addr):
    return self.rfunc[width](addr)
  
  # for derived classes without trace
  def write_mem_int(self, width, addr, val):
    self.wfunc[width](addr, val)
  
  def w_data(self, addr, data):
    off = addr - self.addr
    for d in data:
      self.buffer[off] = d
      off += 1
    self.trace_block_write( addr, len(data))
  
  def r_data(self, addr, size):
    off = addr - self.addr
    result = ""
    for i in xrange(size):
      result += self.buffer[off]
      off += 1
    self.trace_block_read( addr, size )
    return result

  def r_cstr(self, addr):
    off = addr - self.addr
    res = ""
    l = 0
    while self.buffer[off] != '\0':
      res += self.buffer[off]
      off += 1
      l += 1
    self.trace_block_read( addr, l, text="CSTR", addon="'%s'"%res, level=logging.INFO )
    return res

  def w_cstr(self, addr, cstr):
    off = addr - self.addr
    for c in cstr:
      self.buffer[off] = c
      off += 1
    self.buffer[off] = '\0'
    self.trace_block_write( addr, len(cstr), text="CSTR", addon="'%s'"%cstr, level=logging.INFO )

  def r_bstr(self, addr):
    off = addr - self.addr
    res = ""
    size = ord(self.buffer[off])
    off += 1
    for i in xrange(size):
      res += self.buffer[off]
      off += 1
    self.trace_block_read( addr, size, text='BSTR', addon="'%s'"%res, level=logging.INFO )
    return res

  def w_bstr(self, addr, bstr):
    off = addr - self.addr
    size = len(bstr)
    self.buffer[off] = chr(size)
    off += 1
    for c in bstr:
      self.buffer[off] = c
      off += 1
    self.trace_block_write( addr, size, text='BSTR', addon="'%s'"%bstr, level=logging.INFO )

    
    