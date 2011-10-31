import ctypes
import struct

from Exceptions import *
from AccessMemory import AccessMemory

# MainMemory manages the whole address map of the CPU
# Its divided up into pages of 64K
# So every address can be written as:
#
# xxyyyy -> page xx offset yyyy

class MainMemory:
  
  op_reset = 0x04e70
  
  def __init__(self, label_mgr, error_tracker):
    self.error_tracker = error_tracker
    self.label_mgr = label_mgr
    self.access = AccessMemory(self, label_mgr)

    self.read_page_func = []
    self.write_page_func = []
    for i in xrange(256):
      self.read_page_func.append((self.r8_fail, self.r16_fail, self.r32_fail))
      self.write_page_func.append((self.w8_fail, self.w16_fail, self.w32_fail))
    self.special_page = 256
  
  # allocate the RAM area
  def init_ram(self, ram_size):
    self.ram_pages = ram_size / 64
    self.ram_bytes = self.ram_pages * 65536
    self.ram_data = ctypes.create_string_buffer( self.ram_bytes )
    for i in xrange(self.ram_pages):
      self.read_page_func[i] = (self.r8_ram, self.r16_ram, self.r32_ram)
      self.write_page_func[i] = (self.w8_ram, self.w16_ram, self.w32_ram)

  # reserve special range -> begin_addr
  def reserve_special_range(self, num_pages=1):
    begin_page = self.special_page - num_pages
    if begin_page < self.ram_pages:
      raise ValueError("No space left for special page")
    self.special_page -= num_pages
    return begin_page << 16
    
  def set_special_range_read_funcs(self, addr, num_pages=1, r8=None, r16=None, r32=None):
    page = addr >> 16
    if r8 == None:
      r8 = self.r8_fail
    if r16 == None:
      r16 = self.r16_fail
    if r32 == None:
      r32 = self.r32_fail
    for i in xrange(num_pages):
      self.read_page_func[page+i] = (r8, r16, r32)

  def set_special_range_write_funcs(self, addr, num_pages=1, w8=None, w16=None, w32=None):
    page = addr >> 16
    if w8 == None:
      w8 = self.w8_fail
    if w16 == None:
      w16 = self.w16_fail
    if w32 == None:
      w32 = self.w32_fail
    for i in xrange(num_pages):
      self.write_page_func[page+i] = (w8, w16, w32)

  def set_all_to_end(self):
    for i in xrange(256):
      self.read_page_func[i] = (self.r8_end, self.r16_end, self.r32_end)
      self.write_page_func[i] = (self.w8_end, self.w16_end, self.w32_end)      

  # get CPU memory functions
  def get_read_funcs(self, memory_trace):
    if memory_trace:
      return ( self.r8t, self.r16t, self.r32t )
    else:
      return ( self.r8, self.r16, self.r32 )      
  def get_write_funcs(self, memory_trace):
    if memory_trace:
      return ( self.w8t, self.w16t, self.w32t )
    else:
      return ( self.w8, self.w16, self.w32 )
  
  # end CPU operation by returning only RESETs
  def r8_end(self,addr):
    return 0
  def r16_end(self,addr):
    return self.op_reset
  def r32_end(self,addr):
    return 0

  def w8_end(self,addr,v):
    pass
  def w16_end(self,addr,v):
    pass
  def w32_end(self,addr,v):
    pass
  
  # invalid memory access
  def r8_fail(self,addr):
    self.error_tracker.report_error(InvalidMemoryAccessError('R',0,addr))
    self.set_all_to_end()
    return 0
  def r16_fail(self,addr):
    self.error_tracker.report_error(InvalidMemoryAccessError('R',1,addr))
    self.set_all_to_end()
    return 0
  def r32_fail(self,addr):
    self.error_tracker.report_error(InvalidMemoryAccessError('R',2,addr))
    self.set_all_to_end()
    return 0
    
  def w8_fail(self,addr,v):
    self.error_tracker.report_error(InvalidMemoryAccessError('W',0,addr))
    self.set_all_to_end()
  def w16_fail(self,addr,v):
    self.error_tracker.report_error(InvalidMemoryAccessError('W',1,addr))
    self.set_all_to_end()
  def w32_fail(self,addr,v):
    self.error_tracker.report_error(InvalidMemoryAccessError('W',2,addr))
    self.set_all_to_end()

  # RAM access
  def r8_ram(self, addr):
    return struct.unpack_from("B",self.ram_data,offset=addr)[0]
  def r16_ram(self, addr):
    return struct.unpack_from(">H",self.ram_data,offset=addr)[0]
  def r32_ram(self, addr):
    return struct.unpack_from(">I",self.ram_data,offset=addr)[0]

  def w8_ram(self, addr, v):
    struct.pack_into("B",self.ram_data,addr,v)
  def w16_ram(self, addr, v):
    struct.pack_into(">H",self.ram_data,addr,v)
  def w32_ram(self, addr, v):
    struct.pack_into(">I",self.ram_data,addr,v)

  # dispatch access
  def r8(self, addr):
    page = addr >> 16
    return self.read_page_func[page][0](addr)
  def r16(self, addr):
    page = addr >> 16
    return self.read_page_func[page][1](addr)
  def r32(self, addr):
    page = addr >> 16
    return self.read_page_func[page][2](addr)
  
  def w8(self, addr, val):
    page = addr >> 16
    self.write_page_func[page][0](addr, val)  
  def w16(self, addr, val):
    page = addr >> 16
    self.write_page_func[page][1](addr, val)
  def w32(self, addr, val):
    page = addr >> 16
    self.write_page_func[page][2](addr, val)
      
  # dispatch access with memory trace enabled
  def r8t(self, addr):
    page = addr >> 16
    val = self.read_page_func[page][0](addr)
    self.label_mgr.trace_mem('R',0,addr,val)
    return val
  def r16t(self, addr):
    page = addr >> 16
    val = self.read_page_func[page][1](addr)
    self.label_mgr.trace_mem('R',1,addr,val)
    return val
  def r32t(self, addr):
    page = addr >> 16
    val = self.read_page_func[page][2](addr)
    self.label_mgr.trace_mem('R',2,addr,val)
    return val

  def w8t(self, addr, val):
    page = addr >> 16
    self.write_page_func[page][0](addr, val)
    self.label_mgr.trace_mem('W',0,addr,val)
  def w16t(self, addr, val):
    page = addr >> 16
    self.write_page_func[page][1](addr, val)
    self.label_mgr.trace_mem('W',1,addr,val)
  def w32t(self, addr, val):
    page = addr >> 16
    self.write_page_func[page][2](addr, val)
    self.label_mgr.trace_mem('W',2,addr,val)
      
  # this is used by Access classes
  # (do no trace these calls as they are not origin from the CPU!)
  def read_mem(self, width, addr):
    page = addr >> 16
    return self.read_page_func[page][width](addr)
  def write_mem(self, width, addr, val):
    page = addr >> 16
    self.write_page_func[page][width](addr, val)
