import logging

class AccessMemory:
  # set this label manager to enable memory tracing!
  label_mgr = None

  def __init__(self, mem):
    self.mem = mem
    self.raw_mem = mem.raw_mem

  # memory access
  def rx(self, addr, width):
    if width == 0:
      return r8(addr)
    elif width == 1:
      return r16(addr)

  def r32(self, addr):
    val = self.raw_mem.r32(addr)
    if self.label_mgr != None:
      self.label_mgr.trace_int_mem('R', 2, addr, val)
    return val

  def r16(self, addr):
    val = self.raw_mem.r16(addr)
    if self.label_mgr != None:
      self.label_mgr.trace_int_mem('R', 1, addr, val)
    return val

  def r8(self, addr):
    val = self.raw_mem.r8(addr)
    if self.label_mgr != None:
      self.label_mgr.trace_int_mem('R', 0, addr, val)
    return self.read_mem(0, addr)

  def w32(self, addr, val):
    self.raw_mem.w32(addr, val)
    if self.label_mgr != None:
      self.label_mgr.trace_int_mem('W', 2, addr, val)

  def w16(self, addr, val):
    self.raw_mem.w16(addr, val)
    if self.label_mgr != None:
      self.label_mgr.trace_int_mem('W', 1, addr, val)

  def w8(self, addr, val):
    self.raw_mem.w8(addr, val)
    if self.label_mgr != None:
      self.label_mgr.trace_int_mem('W', 0, addr, val)

  # arbitrary width
  def read_mem(self, width, addr):
    val = self.raw_mem.read(width, addr)
    if self.label_mgr != None:
      self.label_mgr.trace_int_mem('R', width, addr, val)
    return val

  def write_mem(self, width, addr, value):
    self.raw_mem.write(width, addr, value)
    if self.label_mgr != None:
      self.label_mgr.trace_int_mem('W', width, addr, val)

  # block access
  def w_data(self, addr, data):
    self.raw_mem.w_block(addr, data)
    if self.label_mgr != None:
      self.label_mgr.trace_int_block( 'W', addr, len(data) )

  def r_data(self, addr, size):
    data = self.raw_mem.r_block(addr, size)
    if self.label_mgr != None:
      self.label_mgr.trace_int_block( 'R', addr, size )
    return data

  def clear_data(self, addr, size, value):
    self.raw_mem.clear_block(addr, size, value)

  # c string
  def r_cstr(self, addr):
    if addr == 0:
      # THOR: Some buggy programs pass a NULL pointer and expect that
      # location zero reads zero (which it does by default)
      cstr = ""
    else:
      cstr = self.raw_mem.r_cstr(addr)
    if self.label_mgr != None:
      self.label_mgr.trace_int_block( 'R', addr, len(cstr), text="CSTR", addon="'%s'"%cstr, level=logging.INFO )
    return cstr

  def w_cstr(self, addr, cstr):
    if addr != 0:
      self.raw_mem.w_cstr(addr, cstr)
      if self.label_mgr != None:
        self.label_mgr.trace_int_block( 'W', addr, len(cstr), text="CSTR", addon="'%s'"%cstr, level=logging.INFO )

  def r_bstr(self, addr):
    if addr == 0:
      bstr = ""
    else:
      bstr = self.raw_mem.r_bstr(addr)
    if self.label_mgr != None:
      self.label_mgr.trace_int_block( 'R', addr, len(bstr), text='BSTR', addon="'%s'"%bstr, level=logging.INFO )
    return bstr

  def w_bstr(self, addr, bstr):
    if addr != 0:
      self.raw_mem.w_bstr(addr, bstr)
      if self.label_mgr != None:
        self.label_mgr.trace_int_block( 'W', addr, len(bstr), text='BSTR', addon="'%s'"%bstr, level=logging.INFO )
