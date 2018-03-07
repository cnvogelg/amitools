# various Amiga Math utils

import struct
import math

#taken from http://www.neotitans.com/resources/python/python-unsigned-32bit-value.html
#Casting Python integers into signed 32-bit equivalents
def int32(x):
  if x > 0xFFFFFFFF:
    raise OverflowError
  if x > 0x7FFFFFFF:
    x = int(0x100000000 - x)
    if x < 2147483648:
      return -x
    else:
      return -2147483648
  return x

def double_to_regs(number):
  """convert Python double to (hi, lo) reg pair"""
  st = struct.pack('>d', number)
  return struct.unpack('>LL',st)

def regs_to_double(hi,lo):
  """convert (hi, lo) Amiga reg pair to double"""
  st = struct.pack('>LL', hi, lo)
  return struct.unpack('>d', st)[0]

def float_to_reg(number):
  """convert Python float to reg value"""
  st = struct.pack('>f', number)
  return struct.unpack('>L',st)[0]

def reg_to_float(reg):
  """convert reg value to Python float"""
  st = struct.pack('>L', reg)
  return struct.unpack('>f',st)[0]

# Amiga constants

Amiga_INT_MAX = 2147483647
Amiga_INT_MIN = -2147483648

Amiga_DBL_POS_MAX = regs_to_double(0x7fefffff, 0xffffffff)
Amiga_DBL_NEG_MAX = regs_to_double(0xffefffff, 0xffffffff)
Amiga_DBL_NAN1 =    regs_to_double(0x7ff10000, 0x00000000)

Amiga_FLT_POS_MAX = reg_to_float(0x7F7FFFFF)
Amiga_FLT_NEG_MAX = reg_to_float(0xFF7FFFFF)
