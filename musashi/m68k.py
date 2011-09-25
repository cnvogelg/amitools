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

# define function types for callbacks
read_func_type = CFUNCTYPE(c_uint, c_uint)
write_func_type = CFUNCTYPE(None, c_uint, c_uint)
monitor_func_type = CFUNCTYPE(None, c_uint)

# declare functions
execute_func = lib.m68k_execute
execute_func.restype = c_int
execute_func.argtypes = [c_int]

get_reg_func = lib.m68k_get_reg
get_reg_func.restype = c_uint
get_reg_func.argtypes = [c_void_p, c_int]

set_reg_func = lib.m68k_set_reg
set_reg_func.argtypes = [c_int, c_uint]

# --- API ---

def set_read_memory(r8, r16, r32):
  global r8c, r16c, r32c
  r8c = read_func_type(r8)
  r16c = read_func_type(r16)
  r32c = read_func_type(r32)
  lib.m68k_set_read_memory(r8c, r16c, r32c)

def set_write_memory(w8, w16, w32):
  global w8c, w16c, w32c
  w8c = write_func_type(w8)
  w16c = write_func_type(w16)
  w32c = write_func_type(w32)
  lib.m68k_set_write_memory(w8c, w16c, w32c)

def set_pc_changed_callback(func):
  f = monitor_func_type(func)
  lib.m68k_set_pc_changed_callback(f)

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

# --- Sample ---

if __name__ == "__main__":
  def read_mem_8(addr):
    print "read 8 %08x" % (addr)
    return 0

  def read_mem_16(addr):
    print "read 16 %08x" % (addr)
    return 0

  def read_mem_32(addr):
    print "read 32 %08x" % (addr)
    return 0

  def write_mem_8(addr, value):
    print "write 8 %08x: %08x" % (addr,value)

  def write_mem_16(addr, value):
    print "write 16 %08x: %08x" % (addr,value)

  def write_mem_32(addr, value):
    print "write 32 %08x: %08x" % (addr,value)
  
  def pc_changed(addr):
    print "pc %08x" % (addr)
  
  set_read_memory(read_mem_8, read_mem_16, read_mem_32)
  set_write_memory(write_mem_8, write_mem_16, write_mem_32)
  set_cpu_type(M68K_CPU_TYPE_68000)
  set_pc_changed_callback(pc_changed)
  
  print "resetting cpu..."
  pulse_reset()
  print "executing..."
  set_reg(M68K_REG_PC,0xf80000);
  print execute(100)
  
  print "get/set register"
  print "%08x" % get_reg(M68K_REG_D0)
  set_reg(M68K_REG_D0,0xdeadbeef)
  print "%08x" % get_reg(M68K_REG_D0)
  