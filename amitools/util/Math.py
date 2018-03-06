# various Amiga Math utils

import struct
import math

Amiga_INT_MAX = 2147483647
Amiga_INT_MIN = -2147483648

Amiga_DBL_POS_INF = (0x7fefffff, 0xffffffff)
Amiga_DBL_NEG_INF = (0xffefffff, 0xffffffff)
Amiga_DBL_NAN =     (0x7ff10000, 0x00000000)

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

def double_to_regs(number, force_pos_zero=False):
  """convert Python double to (hi, lo) reg pair"""
  if math.isnan(number):
    return Amiga_DBL_NAN
  elif math.isinf(number):
    if number > 0.0:
      return Amiga_DBL_POS_INF
    else:
      return Amiga_DBL_NEG_INF
  else:
    st = struct.pack('>d', number)
    hi, lo = struct.unpack('>LL',st)
    # on amiga zero is sometimes positive
    if force_pos_zero:
      if hi==0x80000000 and lo==0x00000000:
        hi=0x00000000
    return hi, lo

def regs_to_double(hi,lo):
  """convert (hi, lo) Amiga reg pair to double"""
  st = struct.pack('>LL', hi, lo)
  return struct.unpack('>d', st)[0]
