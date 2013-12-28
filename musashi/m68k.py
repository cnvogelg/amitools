#!/usr/bin/env python
#
# m68k.py
#
# wrapper for musashi m68k CPU emulator
#

import os
from ctypes import *
import ctypes.util

# --- Constants ---

# cpu type
M68K_CPU_TYPE_INVALID = 0
M68K_CPU_TYPE_68000 = 1
M68K_CPU_TYPE_68010 = 2
M68K_CPU_TYPE_68EC020 = 3
M68K_CPU_TYPE_68020 = 4
M68K_CPU_TYPE_68030 = 5 # Supported by disassembler ONLY
M68K_CPU_TYPE_68040	= 6 # Supported by disassembler ONLY

# registers
M68K_REG_D0 = 0
M68K_REG_D1 = 1
M68K_REG_D2 = 2
M68K_REG_D3 = 3
M68K_REG_D4 = 4
M68K_REG_D5 = 5
M68K_REG_D6 = 6
M68K_REG_D7 = 7
M68K_REG_A0 = 8
M68K_REG_A1 = 9
M68K_REG_A2 = 10
M68K_REG_A3 = 11
M68K_REG_A4 = 12
M68K_REG_A5 = 13
M68K_REG_A6 = 14
M68K_REG_A7 = 15
M68K_REG_PC = 16 # Program Counter
M68K_REG_SR = 17 # Status Register
M68K_REG_SP = 18 #The current Stack Pointer (located in A7)
M68K_REG_USP = 19 # User Stack Pointer
M68K_REG_ISP = 20 # Interrupt Stack Pointer
M68K_REG_MSP = 21 # Master Stack Pointer
M68K_REG_SFC = 22 # Source Function Code
M68K_REG_DFC = 23 # Destination Function Code
M68K_REG_VBR = 24 # Vector Base Register
M68K_REG_CACR = 25 # Cache Control Register
M68K_REG_CAAR = 26 # Cache Address Register

M68K_REG_PREF_ADDR = 27 # Virtual Reg: Last prefetch address
M68K_REG_PREF_DATA = 28 # Virtual Reg: Last prefetch data

M68K_REG_PPC = 29 # Previous value in the program counter
M68K_REG_IR = 30 # Instruction register
M68K_REG_CPU_TYPE = 31 # Type of CPU being run

# --- Internal ---

# get lib
def find_lib():
  path = os.path.dirname(os.path.realpath(__file__))
  all_files = os.listdir(path)
  for f in all_files:
    if f.find('musashi') != -1:
      return os.path.join(path,f)
  raise ImportError("Can't find musashi native lib")
 
lib_file = find_lib()
lib = CDLL(lib_file)

# define CPU function types for callbacks
read_func_type = CFUNCTYPE(c_uint, c_uint)
write_func_type = CFUNCTYPE(None, c_uint, c_uint)
pc_changed_callback_func_type = CFUNCTYPE(None, c_uint)
reset_instr_callback_func_type = CFUNCTYPE(None)
invalid_func_type = CFUNCTYPE(None, c_int, c_int, c_uint)
trace_func_type = CFUNCTYPE(c_int, c_int, c_int, c_uint, c_uint)
instr_hook_callback_func = CFUNCTYPE(None)
aline_hook_callback_func = CFUNCTYPE(c_int, c_uint, c_uint)

trap_func = CFUNCTYPE(None, c_uint, c_uint)

# declare cpu functions
cpu_init_func = lib.m68k_init

execute_func = lib.m68k_execute
execute_func.restype = c_int
execute_func.argtypes = [c_int]

get_reg_func = lib.m68k_get_reg
get_reg_func.restype = c_uint
get_reg_func.argtypes = [c_void_p, c_int]

set_reg_func = lib.m68k_set_reg
set_reg_func.argtypes = [c_int, c_uint]

disassemble_func = lib.m68k_disassemble
disassemble_func.restype = c_int
disassemble_func.argtypes = [c_char_p, c_uint, c_uint]

# declare mem functions
mem_init_func = lib.mem_init
mem_init_func.restype = c_int
mem_init_func.argtypes = [c_uint]

mem_free_func = lib.mem_free

mem_set_trace_mode_func = lib.mem_set_trace_mode
mem_set_trace_mode_func.argtypes = [c_int]

mem_is_end_func = lib.mem_is_end
mem_is_end_func.restype = c_int

mem_reserve_special_range_func = lib.mem_reserve_special_range
mem_reserve_special_range_func.restype = c_uint
mem_reserve_special_range_func.argtypes = [c_uint]

mem_set_special_range_read_func_func = lib.mem_set_special_range_read_func
mem_set_special_range_read_func_func.argtypes = [c_uint, c_uint, read_func_type]

mem_set_special_range_write_func_func = lib.mem_set_special_range_write_func
mem_set_special_range_write_func_func.argtypes = [c_uint, c_uint, write_func_type]

# public
mem_ram_read = lib.mem_ram_read
mem_ram_read.restype = c_uint
mem_ram_read.argtypes = [c_int, c_uint]

mem_ram_write = lib.mem_ram_write
mem_ram_write.argtypes = [c_int, c_uint, c_uint]

mem_ram_read_block = lib.mem_ram_read_block
mem_ram_read_block.argtypes = [c_uint, c_uint, c_char_p]

mem_ram_write_block = lib.mem_ram_write_block
mem_ram_write_block.argtypes = [c_uint, c_uint, c_char_p]

mem_ram_clear_block = lib.mem_ram_clear_block
mem_ram_clear_block.argtypes = [c_uint, c_uint, c_int]

# trap functions
trap_init_func = lib.trap_init

trap_setup_func = lib.trap_setup
trap_setup_func.restype = c_uint
trap_setup_func.argtypes = [trap_func]

trap_free_func = lib.trap_free
trap_free_func.argtypes = [c_int]

# --- CPU API ---

def cpu_init():
  cpu_init_func()

def set_pc_changed_callback(func):
  global pc_changed_callback
  pc_changed_callback = pc_changed_callback_func_type(func)
  lib.m68k_set_pc_changed_callback(pc_changed_callback)

def set_reset_instr_callback(func):
  global reset_instr_callback
  reset_instr_callback = reset_instr_callback_func_type(func)
  lib.m68k_set_reset_instr_callback(reset_instr_callback)

def set_instr_hook_callback(func):
  global instr_hook_callback
  instr_hook_callback = instr_hook_callback_func(func)
  lib.m68k_set_instr_hook_callback(instr_hook_callback)

def set_aline_hook_callback(func):
  global aline_hook_callback
  aline_hook_callback = aline_hook_callback_func(func)
  lib.m68k_set_aline_hook_callback(aline_hook_callback)

def set_cpu_type(t):
  lib.m68k_set_cpu_type(c_uint(t))

def pulse_reset():
  lib.m68k_pulse_reset()

def execute(cycles):
  return execute_func(cycles)

def get_reg(reg):
  return get_reg_func(None, reg)

def set_reg(reg, value):
  set_reg_func(reg, value)

def end_timeslice():
  lib.m68k_end_timeslice()

def disassemble(pc, cpu_type):
  p = create_string_buffer(80)
  n = disassemble_func(p, pc, cpu_type)
  return p.value

# --- MEM API ---

def mem_init(ram_size_kib):
  return mem_init_func(ram_size_kib)

def mem_free():
  mem_free_func()

def mem_set_invalid_func(func):
  global invalid_func_callback
  invalid_func_callback = invalid_func_type(func)
  lib.mem_set_invalid_func(invalid_func_callback)

def mem_set_trace_mode(on):
  mem_set_trace_mode_func(on)

def mem_set_trace_func(func):
  global trace_func_callback
  trace_func_callback = trace_func_type(func)
  lib.mem_set_trace_func(trace_func_callback)
  
def mem_is_end():
  return mem_is_end_func()
  
def mem_reserve_special_range(num_pages=1):
  return mem_reserve_special_range_func(num_pages)

w_funcs = {}
r_funcs = {}

def mem_set_special_range_read_func(page_addr, width, func):
  global r_funcs
  key = "%06x_%d" % (page_addr, width)
  f = read_func_type(func)
  r_funcs[key] = f
  mem_set_special_range_read_func_func(page_addr, width, f)

def mem_set_special_range_write_func(page_addr, width, func):
  global w_funcs
  key = "%06x_%d" % (page_addr, width)
  f = write_func_type(func)
  w_funcs[key] = f
  mem_set_special_range_write_func_func(page_addr, width, f)

# --- Traps ---

def trap_init():
  global _traps
  trap_init_func()
  _traps = {}

def trap_setup(func):
  global _traps
  f = trap_func(func)
  tid = trap_setup_func(f)
  _traps[tid] = f
  return tid
  
def trap_free(tid):
  global _traps
  del _traps[tid]
  trap_free_func(tid)

# --- Sample ---

if __name__ == "__main__":
  print "init cpu"
  cpu_init()
  
  print "init mem"
  if not mem_init(128):
    print "ERROR: OUT OF MEMORY"

  spec_addr = mem_reserve_special_range()
  print "special range: %06x" % spec_addr

  def invalid(mode, width, addr):
    print "MY INVALID: %s(%d): %06x" % (chr(mode), width, addr)
  
  def trace(mode, width, addr, value):
    print "TRACE: %s(%d): %06x: %x" % (chr(mode), width, addr, value)
    return 0
  
  mem_set_invalid_func(invalid)
  mem_set_trace_func(trace)
  mem_set_trace_mode(1)
  
  def pc_changed(addr):
    print "pc %06x" % (addr)
    
  def reset_handler():
    print "RESET"
  
  set_cpu_type(M68K_CPU_TYPE_68000)
  set_pc_changed_callback(pc_changed)
  set_reset_instr_callback(reset_handler)
  
  print "resetting cpu..."
  pulse_reset()
  
  # write mem
  print "write mem..."
  mem_ram_write(1, 0x1000, 0x4e70) # RESET
  val = mem_ram_read(1, 0x1000)
  print "RESET op=%04x" % val
  
  # write block
  p = create_string_buffer(20)
  mem_ram_write_block(0, 20, p)
  mem_ram_read_block(0, 20, p)
  
  # valid range
  print "executing..."
  set_reg(M68K_REG_PC,0x1000)
  print execute(2)

  def my_r16(addr):
    print "MY RANGE: %06x" % addr
    return 0;
  mem_set_special_range_read_func(spec_addr, 1, my_r16)

  # invalid range
  print "executing invalid..."
  set_reg(M68K_REG_PC,spec_addr)
  print execute(2)
  
  # check invalid a-line opcode hook function
  def my_aline(op, pc):
    print "ALINE: %04x @ %08x" % (op, pc)
    return 1
  print "--- aline ---"
  set_aline_hook_callback(my_aline)
  mem_ram_write(1, 0x2000, 0xa123) # a-line opcode
  set_reg(M68K_REG_PC,0x2000)
  print "testing a-line opcode"
  print execute(2)
  
  # test traps
  print "--- traps ---"
  trap_init()
  def my_trap(op, pc):
    print "MY TRAP: %04x @ %08x" % (op, pc)
  tid = trap_setup(my_trap)
  print "trap id=",tid
  
  # call trap
  mem_ram_write(1, 0x2000, 0xa000 + tid)
  set_reg(M68K_REG_PC,0x2000)
  print "call trap"
  print execute(2)
  
  # free trap
  trap_free(tid)
  
  # check if mem is in end mode?
  is_end = mem_is_end()
  print "mem is_end:",is_end
  
  print "get/set register"
  print "%08x" % get_reg(M68K_REG_D0)
  set_reg(M68K_REG_D0,0xdeadbeef)
  print "%08x" % get_reg(M68K_REG_D0)
  
  mem_free()
  print "done"
