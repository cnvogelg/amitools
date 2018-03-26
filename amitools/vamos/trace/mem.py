import logging


class TraceMemory:
  def __init__(self, mem, trace_mgr):
    """a front-end class to memory that does tracing"""
    self.mem = mem
    self.trace_mgr = trace_mgr

  # memory access
  def r32(self, addr):
    val = self.mem.r32(addr)
    self.trace_mgr.trace_int_mem('R', 2, addr, val)
    return val

  def r16(self, addr):
    val = self.mem.r16(addr)
    self.trace_mgr.trace_int_mem('R', 1, addr, val)
    return val

  def r8(self, addr):
    val = self.mem.r8(addr)
    self.trace_mgr.trace_int_mem('R', 0, addr, val)
    return val

  def w32(self, addr, val):
    self.mem.w32(addr, val)
    self.trace_mgr.trace_int_mem('W', 2, addr, val)

  def w16(self, addr, val):
    self.mem.w16(addr, val)
    self.trace_mgr.trace_int_mem('W', 1, addr, val)

  def w8(self, addr, val):
    self.mem.w8(addr, val)
    self.trace_mgr.trace_int_mem('W', 0, addr, val)

  # signed memory access
  def r32s(self, addr):
    val = self.mem.r32s(addr)
    self.trace_mgr.trace_int_mem('R', 2, addr, val)
    return val

  def r16s(self, addr):
    val = self.mem.r16s(addr)
    self.trace_mgr.trace_int_mem('R', 1, addr, val)
    return val

  def r8s(self, addr):
    val = self.mem.r8s(addr)
    self.trace_mgr.trace_int_mem('R', 0, addr, val)
    return val

  def w32s(self, addr, val):
    self.mem.w32s(addr, val)
    self.trace_mgr.trace_int_mem('W', 2, addr, val)

  def w16s(self, addr, val):
    self.mem.w16s(addr, val)
    self.trace_mgr.trace_int_mem('W', 1, addr, val)

  def w8s(self, addr, val):
    self.mem.w8s(addr, val)
    self.trace_mgr.trace_int_mem('W', 0, addr, val)

  # arbitrary width
  def read(self, width, addr):
    val = self.mem.read(width, addr)
    self.trace_mgr.trace_int_mem('R', width, addr, val)
    return val

  def write(self, width, addr, val):
    self.mem.write(width, addr, val)
    self.trace_mgr.trace_int_mem('W', width, addr, val)

  # signed arbitrary width
  def reads(self, width, addr):
    val = self.mem.reads(width, addr)
    self.trace_mgr.trace_int_mem('R', width, addr, val)
    return val

  def writes(self, width, addr, val):
    self.mem.writes(width, addr, val)
    self.trace_mgr.trace_int_mem('W', width, addr, val)

  # block access
  def w_block(self, addr, data):
    self.mem.w_block(addr, data)
    self.trace_mgr.trace_int_block('W', addr, len(data))

  def r_block(self, addr, size):
    data = self.mem.r_block(addr, size)
    self.trace_mgr.trace_int_block('R', addr, size)
    return data

  def clear_block(self, addr, size, value):
    self.mem.clear_block(addr, size, value)
    self.trace_mgr.trace_int_block('F', addr, size)

  def copy_block(self, src_addr, tgt_addr, size):
    self.mem.copy_block(src_addr, tgt_addr, size)
    self.trace_mgr.trace_int_block('C', tgt_addr, size)

  # string
  def r_cstr(self, addr):
    cstr = self.mem.r_cstr(addr)
    self.trace_mgr.trace_int_block('R', addr, len(cstr),
      text="CSTR", addon="'%s'" % cstr)
    return cstr

  def w_cstr(self, addr, cstr):
    self.mem.w_cstr(addr, cstr)
    self.trace_mgr.trace_int_block('W', addr, len(cstr),
      text="CSTR", addon="'%s'" % cstr)

  def r_bstr(self, addr):
    bstr = self.mem.r_bstr(addr)
    self.trace_mgr.trace_int_block('R', addr, len(bstr),
      text='BSTR', addon="'%s'" % bstr)
    return bstr

  def w_bstr(self, addr, bstr):
    self.mem.w_bstr(addr, bstr)
    self.trace_mgr.trace_int_block('W', addr, len(bstr),
      text='BSTR', addon="'%s'" % bstr)
