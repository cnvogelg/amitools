import logging
import ctypes

class AccessMemory:
  # set this label manager to enable memory tracing!
  label_mgr = None
  
  def __init__(self, mem):
    self.mem = mem

  def write_mem(self, width, addr, val):
    self.mem.write_mem(width, addr, val)
    if self.label_mgr != None:
      self.label_mgr.trace_int_mem('W',width, addr, val)

  def read_mem(self, width, addr):
    val = self.mem.read_mem(width, addr)
    if self.label_mgr != None:
      self.label_mgr.trace_int_mem('R',width, addr, val)
    return val

  def r32(self, addr):
    return self.read_mem(2, addr)
  
  def r16(self, addr):
    return self.read_mem(1, addr)
  
  def r8(self, addr):
    return self.read_mem(0, addr)

  def w32(self, addr, val):
    self.write_mem(2, addr, val)

  def w16(self, addr, val):
    self.write_mem(1, addr, val)

  def w8(self, addr, val):
    self.write_mem(0, addr, val)

  def w_data(self, addr, data):
    size = len(data)
    buf = ctypes.create_string_buffer(data)
    self.mem.write_block(addr,size,buf)
    if self.label_mgr != None:
      self.label_mgr.trace_int_block( 'W', addr, size )

  def r_data(self, addr, size):
    buf = ctypes.create_string_buffer(size)
    self.mem.read_block(addr,size,buf)
    if self.label_mgr != None:
      self.label_mgr.trace_int_block( 'R', addr, size )
    return buf.raw

  def r_cstr(self, addr):
    off = addr
    res = ""
    l = 0
    v = None
    while True:
      v = chr(self.mem.read_mem(0, off))
      if v == '\0':
        break
      res += v
      off += 1
      l += 1
    if self.label_mgr != None:
      self.label_mgr.trace_int_block( 'R', addr, l, text="CSTR", addon="'%s'"%res, level=logging.INFO )
    return res

  def w_cstr(self, addr, cstr):
    off = addr
    for c in cstr:
      self.mem.write_mem(0, off, ord(c))
      off += 1
    self.mem.write_mem(0, off, 0)
    if self.label_mgr != None:
      self.label_mgr.trace_int_block( 'W', addr, len(cstr), text="CSTR", addon="'%s'"%cstr, level=logging.INFO )

  def r_bstr(self, addr):
    off = addr
    res = ""
    size = self.mem.read_mem(0, off)
    off += 1
    for i in xrange(size):
      res += chr(self.mem.read_mem(0, off))
      off += 1
    if self.label_mgr != None:
      self.label_mgr.trace_int_block( 'R', addr, size, text='BSTR', addon="'%s'"%res, level=logging.INFO )
    return res

  def w_bstr(self, addr, bstr):
    off = addr
    size = len(bstr)
    self.mem.write_mem(0, off, size)
    off += 1
    for c in bstr:
      self.mem.write_mem(0, off, ord(c))
      off += 1
    if self.label_mgr != None:
      self.label_mgr.trace_int_block( 'W', addr, size, text='BSTR', addon="'%s'"%bstr, level=logging.INFO )


  