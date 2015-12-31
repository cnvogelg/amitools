# cython binding for musashi

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

  void m68k_set_cpu_type(unsigned int cpu_type);
  void m68k_init()
  void m68k_pulse_reset()
  int m68k_execute(int num_cycles)
  void m68k_end_timeslice()

  unsigned int m68k_get_reg(void* context, m68k_register_t reg)
  void m68k_set_reg(m68k_register_t reg, unsigned int value)

  void m68k_set_pc_changed_callback(void (*callback)(unsigned int new_pc) except *)
  void m68k_set_reset_instr_callback(void (*callback)() except *)
  void m68k_set_instr_hook_callback(void (*callback)() except *)

  unsigned int m68k_disassemble(char* str_buff, unsigned int pc, unsigned int cpu_type)

# wrapper
cdef object pc_changed_func
cdef void pc_changed_func_wrapper(unsigned int new_pc) except *:
  pc_changed_func(new_pc)

cdef object reset_instr_func
cdef void reset_instr_func_wrapper() except *:
  reset_instr_func()

cdef object instr_hook_func
cdef void instr_hook_func_wrapper() except *:
  instr_hook_func()

# public CPU class
cdef class CPU:
  cdef unsigned int cpu_type

  def __cinit__(self, cpu_type):
    m68k_set_cpu_type(cpu_type)
    m68k_init()
    self.cpu_type = cpu_type

  cdef long long r_reg_internal(self,int reg):
      return m68k_get_reg(NULL, <m68k_register_t>reg)

  cdef void w_reg_internal(self,int reg,long long v):
      m68k_set_reg(<m68k_register_t>reg,<unsigned int>(v & 0xffffffff))
                   
  def w_reg(self, reg, val):
    self.w_reg_internal(reg,val)
  
  def r_reg(self,reg):
    return self.r_reg_internal(reg)

  def w_pc(self, val):
    self.w_reg_internal(M68K_REG_PC,val)

  def r_pc(self):
    return self.r_reg_internal(M68K_REG_PC)

  def w_sr(self, val):
    self.w_reg_internal(M68K_REG_SR,val)

  def r_sr(self):
    return self.r_reg_internal(M68K_REG_SR)

  def pulse_reset(self):
    m68k_pulse_reset()

  def execute(self, num_cycles):
    return m68k_execute(num_cycles)

  def end(self):
    m68k_end_timeslice()

  def set_pc_changed_callback(self, py_func):
    global pc_changed_func
    pc_changed_func = py_func
    m68k_set_pc_changed_callback(pc_changed_func_wrapper)

  def set_reset_instr_callback(self, py_func):
    global reset_instr_func
    reset_instr_func = py_func
    m68k_set_reset_instr_callback(reset_instr_func_wrapper)

  def set_instr_hook_callback(self, py_func):
    global instr_hook_func
    instr_hook_func = py_func
    m68k_set_instr_hook_callback(instr_hook_func_wrapper)

  def disassemble(self, unsigned int pc):
    cdef char line[80]
    cdef unsigned int size
    size = m68k_disassemble(line, pc, self.cpu_type)
    return (size, line)
