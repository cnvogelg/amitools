# mem.h
cdef extern from "mem.h":
  ctypedef unsigned int uint
  ctypedef uint (*read_func_t)(uint addr, void *ctx)
  ctypedef void (*write_func_t)(uint addr, uint value, void *ctx)
  ctypedef void (*invalid_func_t)(int mode, int width, uint addr, void *ctx)
  ctypedef void (*trace_func_t)(int mode, int width, uint addr, uint val, void *ctx)

  int mem_init(uint ram_size_kib)
  void mem_free()

  void mem_set_invalid_func(invalid_func_t func, void *ctx)
  void mem_set_trace_mode(int on)
  void mem_set_trace_func(trace_func_t func, void *ctx)

  uint mem_reserve_special_range(uint num_pages)
  void mem_set_special_range_read_func(uint page_addr, uint width, read_func_t func, void *ctx)
  void mem_set_special_range_write_func(uint page_addr, uint width, write_func_t func, void *ctx)

  unsigned int m68k_read_memory_8(unsigned int address)
  unsigned int m68k_read_memory_16(unsigned int address)
  unsigned int m68k_read_memory_32(unsigned int address)

  void m68k_write_memory_8(unsigned int address, unsigned int value)
  void m68k_write_memory_16(unsigned int address, unsigned int value)
  void m68k_write_memory_32(unsigned int address, unsigned int value)

  unsigned char *mem_raw_ptr()
  uint mem_raw_size()

# string.h
from libc.string cimport memcpy, memset, strlen, strcpy
from libc.stdlib cimport malloc, free

# wrapper functions
cdef void trace_func_wrapper(int mode, int width, uint addr, uint val, void *ctx):
  cdef object py_func = <object>ctx
  py_func(chr(mode), width, addr, val)

cdef void invalid_func_wrapper(int mode, int width, uint addr, void *ctx):
  cdef object py_func = <object>ctx
  py_func(chr(mode), width, addr)

cdef uint special_read_func_wrapper(uint addr, void *ctx):
  cdef object py_func = <object>ctx
  return py_func(addr)

cdef void special_write_func_wrapper(uint addr, uint value, void *ctx):
  cdef object py_func = <object>ctx
  py_func(addr, value)

# public Memory class
cdef class Memory:
  cdef uint ram_size_kib
  cdef uint ram_bytes
  cdef unsigned char *ram_ptr
  # keep python refs of callback funcs otherwise wrapper might loose the object
  cdef set special_read_funcs
  cdef set special_write_funcs
  cdef object trace_func
  cdef object invalid_func

  def __cinit__(self, ram_size_kib):
    mem_init(ram_size_kib)
    self.ram_size_kib = ram_size_kib
    self.ram_bytes = ram_size_kib * 1024
    self.ram_ptr = mem_raw_ptr()
    self.special_read_funcs = set()
    self.special_write_funcs = set()

  def cleanup(self):
    self.set_trace_func(None)
    self.set_invalid_func(None)
    self.special_read_funcs.clear()
    self.special_write_funcs.clear()
    mem_free()

  def get_ram_size_kib(self):
    return self.ram_size_kib

  def get_ram_size_bytes(self):
    return self.ram_bytes

  def reserve_special_range(self,num_pages=1):
    return mem_reserve_special_range(num_pages)

  cpdef set_special_range_read_func(self, uint page_addr, uint width, func):
    mem_set_special_range_read_func(page_addr, width, special_read_func_wrapper, <void *>func)
    # keep func ref
    self.special_read_funcs.add(func)

  cpdef set_special_range_write_func(self,uint page_addr, uint width, func):
    mem_set_special_range_write_func(page_addr, width, special_write_func_wrapper, <void *>func)
    # keep func ref
    self.special_write_funcs.add(func)

  def set_special_range_read_funcs(self, uint addr, uint num_pages=1, r8=None, r16=None, r32=None):
    for i in range(num_pages):
      if r8 != None:
        self.set_special_range_read_func(addr, 0, r8)
      if r16 != None:
        self.set_special_range_read_func(addr, 1, r16)
      if r32 != None:
        self.set_special_range_read_func(addr, 2, r32)
      addr += 0x10000

  def set_special_range_write_funcs(self, uint addr, uint num_pages=1, w8=None, w16=None, w32=None):
    for i in xrange(num_pages):
      if w8 != None:
        self.set_special_range_write_func(addr, 0, w8)
      if w16 != None:
        self.set_special_range_write_func(addr, 1, w16)
      if w32 != None:
        self.set_special_range_write_func(addr, 2, w32)
      addr += 0x10000

  def set_trace_mode(self,on):
    mem_set_trace_mode(on)

  def set_trace_func(self,func):
    if func is None:
      mem_set_trace_func(NULL, NULL)
    else:
      mem_set_trace_func(trace_func_wrapper, <void *>func)
    # keep func ref
    self.trace_func = func

  def set_invalid_func(self,func):
    if func is None:
      mem_set_invalid_func(NULL, NULL)
    else:
      mem_set_invalid_func(invalid_func_wrapper, <void *>func)
    # keep func ref
    self.invalid_func = func

  # memory access (full range including special)
  cpdef r8(self, uint addr):
    return m68k_read_memory_8(addr)
  cpdef r16(self, uint addr):
    return m68k_read_memory_16(addr)
  cpdef r32(self, uint addr):
    return m68k_read_memory_32(addr)
  cpdef w8(self, uint addr, uint value):
    if value > 0xff:
      raise OverflowError("value does not fit into byte")
    m68k_write_memory_8(addr, value)
  cpdef w16(self, uint addr, uint value):
    if value > 0xffff:
      raise OverflowError("value does not fit into word")
    m68k_write_memory_16(addr, value)
  cpdef w32(self, uint addr, uint value):
    m68k_write_memory_32(addr, value)

  # signed memory access (full range including special)
  cpdef r8s(self, uint addr):
    cdef uint val = m68k_read_memory_8(addr)
    # sign extend
    if val & 0x80 == 0x80:
      val |= 0xffffff00
    return <int>(val)
  cpdef r16s(self, uint addr):
    cdef uint val = m68k_read_memory_16(addr)
    # sign extend
    if val & 0x8000 == 0x8000:
      val |= 0xffff0000
    return <int>(val)
  cpdef r32s(self, uint addr):
    return <int>m68k_read_memory_32(addr)
  cpdef w8s(self, uint addr, int value):
    if value < -0x80 or value > 0x7f:
      raise OverflowError("value does not fit into byte")
    cdef uint val = <uint>value & 0xff
    m68k_write_memory_8(addr, val)
  cpdef w16s(self, uint addr, int value):
    if value < -0x8000 or value > 0x7fff:
      raise OverflowError("value does not fit into word")
    cdef uint val = <uint>value & 0xffff
    m68k_write_memory_16(addr, val)
  cpdef w32s(self, uint addr, int value):
    m68k_write_memory_32(addr, <uint>value)

  # arbitrary width (full range including special)
  def read(self, uint width, uint addr):
    if width == 0:
      return self.r8(addr)
    elif width == 1:
      return self.r16(addr)
    elif width == 2:
      return self.r32(addr)
    else:
      raise ValueError("invalid width!")
  def write(self, uint width, uint addr, uint value):
    if width == 0:
      self.w8(addr, value)
    elif width == 1:
      self.w16(addr, value)
    elif width == 2:
      self.w32(addr, value)
    else:
      raise ValueError("invalid width!")

  # signed arbitrary width (full range including special)
  def reads(self, uint width, uint addr):
    if width == 0:
      return self.r8s(addr)
    elif width == 1:
      return self.r16s(addr)
    elif width == 2:
      return self.r32s(addr)
    else:
      raise ValueError("invalid width!")
  def writes(self, uint width, uint addr, int value):
    if width == 0:
      self.w8s(addr, value)
    elif width == 1:
      self.w16s(addr, value)
    elif width == 2:
      self.w32s(addr, value)
    else:
      raise ValueError("invalid width!")

  # block access via str/bytearray (only RAM!)
  def r_block(self,uint addr,uint size):
    if (addr+size) > self.ram_bytes:
      raise ValueError("no RAM")
    res = bytearray(size)
    cdef unsigned char *ptr = res
    cdef const unsigned char *ram = self.ram_ptr + addr
    memcpy(ptr, ram, size)
    return res
  def w_block(self,uint addr,data):
    cdef uint size = len(data)
    if (addr+size) > self.ram_bytes:
      raise ValueError("no RAM")
    cdef const unsigned char *ptr = data
    cdef unsigned char *ram = self.ram_ptr + addr
    memcpy(ram, ptr, size)

  def clear_block(self,uint addr,uint size,unsigned char value):
    if (addr+size) > self.ram_bytes:
      raise ValueError("no RAM")
    cdef unsigned char *ram = self.ram_ptr + addr
    memset(ram,value,size)

  def copy_block(self,uint from_addr, uint to_addr, uint size):
    if (from_addr+size) > self.ram_bytes or (to_addr+size) > self.ram_bytes:
      raise ValueError("no RAM")
    cdef unsigned char *from_ptr = self.ram_ptr + from_addr
    cdef unsigned char *to_ptr = self.ram_ptr + to_addr
    memcpy(to_ptr, from_ptr, size)

  # helpers for c-strings (only RAM)
  def r_cstr(self,uint addr):
    if addr > self.ram_bytes:
      raise ValueError("no RAM")
    cdef unsigned char *ram = self.ram_ptr + addr
    cdef bytes result = ram
    return result

  def w_cstr(self,uint addr,bytes string):
    if addr > self.ram_bytes:
      raise ValueError("no RAM")
    cdef const char *ptr = string
    cdef char *ram = <char *>self.ram_ptr + addr
    strcpy(ram, ptr)

  # helpers for bcpl-strings (only RAM)
  def r_bstr(self,uint addr):
    if addr > self.ram_bytes:
      raise ValueError("no RAM")
    cdef uint size
    cdef char *data
    cdef unsigned char *ram = self.ram_ptr + addr + 1
    size = self.ram_ptr[addr]
    data = <char *>malloc(size+1)
    memcpy(data, ram, size)
    data[size] = '\0'
    cdef bytes result = data
    free(data)
    return result

  def w_bstr(self,uint addr,bytes string):
    if addr > self.ram_bytes:
      raise ValueError("no RAM")
    cdef uint size = len(string)
    cdef unsigned char *ptr = string
    cdef unsigned char *ram = self.ram_ptr + addr
    ram[0] = <unsigned char>size
    ram += 1
    memcpy(ram, ptr, size)
