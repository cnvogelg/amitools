# cython binding for musashi

from libc.stdlib cimport malloc, free

# m68k.h
cdef extern from "m68k.h":
  ctypedef enum m68k_register_t:
    M68K_REG_D0, M68K_REG_D1, M68K_REG_D2, M68K_REG_D3,
    M68K_REG_D4, M68K_REG_D5, M68K_REG_D6, M68K_REG_D7,
    M68K_REG_A0, M68K_REG_A1, M68K_REG_A2, M68K_REG_A3,
    M68K_REG_A4, M68K_REG_A5, M68K_REG_A6, M68K_REG_A7,
    M68K_REG_PC, M68K_REG_SR,
    M68K_REG_SP, M68K_REG_USP, M68K_REG_ISP, M68K_REG_MSP,
    M68K_REG_SFC, M68K_REG_DFC,
    M68K_REG_VBR,
    M68K_REG_CACR, M68K_REG_CAAR,
    M68K_REG_PREF_ADDR, M68K_REG_PREF_DATA,
    M68K_REG_PPC, M68K_REG_IR,
    M68K_REG_CPU_TYPE

  void m68k_set_cpu_type(unsigned int cpu_type)
  void m68k_init()
  void m68k_pulse_reset()
  int m68k_execute(int num_cycles)
  void m68k_end_timeslice()

  unsigned int m68k_get_reg(void* context, m68k_register_t reg)
  void m68k_set_reg(m68k_register_t reg, unsigned int value)

  void m68k_set_pc_changed_callback(void (*callback)(unsigned int new_pc))
  void m68k_set_reset_instr_callback(void (*callback)())
  void m68k_set_illg_instr_callback(int (*callback)(int opcode))
  void m68k_set_instr_hook_callback(void (*callback)(unsigned int pc))

  unsigned int m68k_disassemble(char* str_buff, unsigned int pc, unsigned int cpu_type)
  unsigned int m68k_disassemble_raw(char* str_buff, unsigned int pc, const unsigned char* opdata, const unsigned char* argdata, unsigned int cpu_type)

  unsigned int m68k_context_size()
  unsigned int m68k_get_context(void* dst)
  void m68k_set_context(void* dst)

# wrapper
cdef object pc_changed_func
cdef void pc_changed_func_wrapper(unsigned int new_pc):
  pc_changed_func(new_pc)

cdef object reset_instr_func
cdef void reset_instr_func_wrapper():
  reset_instr_func()

cdef object instr_hook_func
cdef void instr_hook_func_wrapper(unsigned int pc):
  instr_hook_func()

# public CPUContext
cdef class CPUContext:
  cdef void *data
  cdef unsigned int size

  def __cinit__(self, unsigned int size):
    self.data = malloc(size)
    if self.data == NULL:
      raise MemoryError()
    self.size = size

  cdef void *get_data(self):
    return self.data

  def r_reg(self, int reg):
    return m68k_get_reg(self.data, <m68k_register_t>reg)

  def r_pc(self):
    return m68k_get_reg(self.data, M68K_REG_PC)

  def r_sp(self):
    return m68k_get_reg(self.data, M68K_REG_SP)

  def r_usp(self):
    return m68k_get_reg(self.data, M68K_REG_USP)

  def r_isp(self):
    return m68k_get_reg(self.data, M68K_REG_ISP)

  def r_msp(self):
    return m68k_get_reg(self.data, M68K_REG_MSP)

  def __dealloc__(self):
    free(self.data)

# public CPU class
cdef class CPU:
  cdef unsigned int cpu_type

  def __cinit__(self, cpu_type):
    m68k_set_cpu_type(cpu_type)
    m68k_init()
    self.cpu_type = cpu_type

  def cleanup(self):
    self.set_pc_changed_callback(None)
    self.set_reset_instr_callback(None)
    self.set_instr_hook_callback(None)

  cdef unsigned int r_reg_internal(self, m68k_register_t reg):
    return m68k_get_reg(NULL, reg)

  cdef void w_reg_internal(self, m68k_register_t reg, unsigned int v):
    m68k_set_reg(reg, v)

  def w_reg(self, reg, val):
    self.w_reg_internal(reg,val)

  def r_reg(self,reg):
    return self.r_reg_internal(reg)

  def ws_reg(self, m68k_register_t reg, int val):
    m68k_set_reg(reg, <unsigned int>(val))

  def rs_reg(self, m68k_register_t reg):
    return <int>m68k_get_reg(NULL, reg)

  def w_pc(self, val):
    self.w_reg_internal(M68K_REG_PC,val)

  def r_pc(self):
    return self.r_reg_internal(M68K_REG_PC)

  def w_sr(self, val):
    self.w_reg_internal(M68K_REG_SR,val)

  def r_sr(self):
    return self.r_reg_internal(M68K_REG_SR)

  def w_usp(self, val):
    self.w_reg_internal(M68K_REG_USP,val)

  def r_usp(self):
    return self.r_reg_internal(M68K_REG_USP)

  def w_isp(self, val):
    self.w_reg_internal(M68K_REG_ISP,val)

  def r_isp(self):
    return self.r_reg_internal(M68K_REG_ISP)

  def w_msp(self, val):
    self.w_reg_internal(M68K_REG_MSP,val)

  def r_msp(self):
    return self.r_reg_internal(M68K_REG_MSP)

  def pulse_reset(self):
    m68k_pulse_reset()

  def execute(self, num_cycles):
    cdef int cycles = m68k_execute(num_cycles)
    check_mem_exc()
    return cycles

  def end(self):
    m68k_end_timeslice()

  def set_pc_changed_callback(self, py_func):
    global pc_changed_func
    pc_changed_func = py_func
    if py_func is None:
      m68k_set_pc_changed_callback(NULL)
    else:
      m68k_set_pc_changed_callback(pc_changed_func_wrapper)

  def set_reset_instr_callback(self, py_func):
    global reset_instr_func
    reset_instr_func = py_func
    if py_func is None:
      m68k_set_reset_instr_callback(NULL)
    else:
      m68k_set_reset_instr_callback(reset_instr_func_wrapper)

  def set_instr_hook_callback(self, py_func):
    global instr_hook_func
    instr_hook_func = py_func
    if py_func is None:
      m68k_set_instr_hook_callback(NULL)
    else:
      m68k_set_instr_hook_callback(instr_hook_func_wrapper)

  def disassemble(self, unsigned int pc):
    cdef char line[80]
    cdef unsigned int size
    size = m68k_disassemble(line, pc, self.cpu_type)
    return (size, line.decode('latin-1'))

  def disassemble_raw(self, unsigned int pc, const unsigned char[::1] raw_mem):
    cdef char line[80]
    cdef unsigned int size
    size = m68k_disassemble_raw(line, pc, &raw_mem[0], NULL, self.cpu_type)
    return (size, line.decode('latin-1'))

  def get_cpu_context(self):
    cdef unsigned int size = m68k_context_size()
    cdef CPUContext ctx = CPUContext(size)
    cdef void *data = ctx.get_data()
    m68k_get_context(data)
    return ctx

  def set_cpu_context(self, CPUContext ctx):
    m68k_set_context(ctx.get_data())
