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
  def reserve_special_range(self, r_funcs=None, w_funcs=None, num_pages=1):
    begin_page = self.special_page - num_pages
    if begin_page < self.ram_pages:
      raise ValueError("No space left for special page")
    self.special_page -= num_pages
    for i in xrange(num_pages):
      if r_funcs != None:
        self.read_page_func[i] = r_funcs
      if w_funcs != None:
        self.write_page_func[i] = w_funcs
    return begin_page << 16

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
    
  # invalid memory access
  def r8_fail(self,addr):
    raise InvalidMemoryAccessError('R',0,addr,'main')
  def r16_fail(self,addr):
    raise InvalidMemoryAccessError('R',1,addr,'main')
  def r32_fail(self,addr):
    raise InvalidMemoryAccessError('R',2,addr,'main')
    
  def w8_fail(self,addr,v):
    raise InvalidMemoryAccessError('W',0,addr,'main')
  def w16_fail(self,addr,v):
    raise InvalidMemoryAccessError('W',1,addr,'main')
  def w32_fail(self,addr,v):
    raise InvalidMemoryAccessError('W',2,addr,'main')

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
    try:
      page = addr >> 16
      return self.read_page_func[page][0](addr)
    except BaseException as e:
      self.error_tracker.report_error(e)
      return 0
      
  def r16(self, addr):
    try:
      page = addr >> 16
      return self.read_page_func[page][1](addr)
    except BaseException as e:
      self.error_tracker.report_error(e)
      return 0
  
  def r32(self, addr):
    try:
      page = addr >> 16
      return self.read_page_func[page][2](addr)
    except BaseException as e:
      self.error_tracker.report_error(e)
      return 0
  
  def w8(self, addr, val):
    try:
      page = addr >> 16
      self.write_page_func[page][0](addr, val)
    except BaseException as e:
      self.error_tracker.report_error(e)
      
  def w16(self, addr, val):
    try:
      page = addr >> 16
      self.write_page_func[page][1](addr, val)
    except BaseException as e:
      self.error_tracker.report_error(e)
      
  def w32(self, addr, val):
    try:
      page = addr >> 16
      self.write_page_func[page][2](addr, val)
    except BaseException as e:
      self.error_tracker.report_error(e)
      
  # dispatch access with memory trace enabled
  def r8t(self, addr):
    try:
      page = addr >> 16
      val = self.read_page_func[page][0](addr)
      self.label_mgr.trace_mem('R',0,addr,val)
      return val
    except BaseException as e:
      self.error_tracker.report_error(e)
      return 0

  def r16t(self, addr):
    try:
      page = addr >> 16
      val = self.read_page_func[page][1](addr)
      self.label_mgr.trace_mem('R',1,addr,val)
      return val
    except BaseException as e:
      self.error_tracker.report_error(e)
      return 0

  def r32t(self, addr):
    try:
      page = addr >> 16
      val = self.read_page_func[page][2](addr)
      self.label_mgr.trace_mem('R',2,addr,val)
      return val
    except BaseException as e:
      self.error_tracker.report_error(e)
      return 0

  def w8t(self, addr, val):
    try:
      page = addr >> 16
      self.write_page_func[page][0](addr, val)
      self.label_mgr.trace_mem('W',0,addr,val)
    except BaseException as e:
      self.error_tracker.report_error(e)

  def w16t(self, addr, val):
    try:
      page = addr >> 16
      self.write_page_func[page][1](addr, val)
      self.label_mgr.trace_mem('W',1,addr,val)
    except BaseException as e:
      self.error_tracker.report_error(e)

  def w32t(self, addr, val):
    try:
      page = addr >> 16
      self.write_page_func[page][2](addr, val)
      self.label_mgr.trace_mem('W',2,addr,val)
    except BaseException as e:
      self.error_tracker.report_error(e)
      
  # this is used by Access classes
  # (do no trace these calls as they are not origin from the CPU!)
  def read_mem(self, width, addr):
    page = addr >> 16
    return self.read_page_func[page][width](addr)
  def write_mem(self, width, addr, val):
    page = addr >> 16
    self.write_page_func[page][width](addr, val)
