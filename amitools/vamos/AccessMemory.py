import logging
from Log import log_mem_int

class AccessMemory():
  trace_val_str = ( "%02x      ", "%04x    ", "%08x" )
  
  def __init__(self, mem, label_mgr):
    self.mem = mem
    self.label_mgr = label_mgr

  def _get_mem_str(self, addr):
    label = self.label_mgr.get_label(addr)
    if label != None:
      return "@%06x +%06x %s" % (label.addr, addr - label.addr, label.name)
    else:
      return "N/A"

  def _trace_block_read(self, addr, size, text="", level=logging.DEBUG, addon=""):
    log_mem_int.log(level, "R(B): %06x: +%06x   %6s  [%s] %s", addr, size, text, self._get_mem_str(addr), addon)  

  def _trace_block_write(self, addr, size, text="", level=logging.DEBUG, addon=""):
    log_mem_int.log(level, "W(B): %06x: +%06x   %6s  [%s] %s", addr, size, text, self._get_mem_str(addr), addon)  

  def _trace_read(self, width, addr, value, text="", level=logging.DEBUG, addon=""):
    val = self.trace_val_str[width] % value
    log_mem_int.log(level, "R(%d): %06x: %s  %6s  [%s] %s", 2**width, addr, val, text, self._get_mem_str(addr), addon)

  def _trace_write(self, width, addr, value, text="", level=logging.DEBUG, addon=""):
    val = self.trace_val_str[width] % value
    log_mem_int.log(level, "W(%d): %06x: %s  %6s  [%s] %s", 2**width, addr, val, text, self._get_mem_str(addr), addon)

  def write_mem(self, width, addr, val):
    self.mem.write_mem(width, addr, val)
    self._trace_write(width, addr, val)

  def read_mem(self, width, addr):
    val = self.mem.read_mem(width, addr)
    self._trace_read(width, addr, val)
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
    off = addr
    for d in data:
      self.mem.write_mem(0, off, ord(d))
      off += 1
    self._trace_block_write( addr, len(data))

  def r_data(self, addr, size):
    off = addr
    result = ""
    for i in xrange(size):
      result += chr(self.mem.read_mem(0, off))
      off += 1
    self._trace_block_read( addr, size )
    return result

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
    self._trace_block_read( addr, l, text="CSTR", addon="'%s'"%res, level=logging.INFO )
    return res

  def w_cstr(self, addr, cstr):
    off = addr
    for c in cstr:
      self.mem.write_mem(0, off, ord(c))
      off += 1
    self.mem.write_mem(0, off, 0)
    self._trace_block_write( addr, len(cstr), text="CSTR", addon="'%s'"%cstr, level=logging.INFO )

  def r_bstr(self, addr):
    off = addr
    res = ""
    size = self.mem.read_mem(0, off)
    off += 1
    for i in xrange(size):
      res += chr(self.mem.read_mem(0, off))
      off += 1
    self._trace_block_read( addr, size, text='BSTR', addon="'%s'"%res, level=logging.INFO )
    return res

  def w_bstr(self, addr, bstr):
    off = addr
    size = len(bstr)
    self.mem.write_mem(0, off, size)
    off += 1
    for c in bstr:
      self.mem.write_mem(0, off, ord(c))
      off += 1
    self._trace_block_write( addr, size, text='BSTR', addon="'%s'"%bstr, level=logging.INFO )


  