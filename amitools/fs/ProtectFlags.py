from __future__ import absolute_import
from __future__ import print_function

from .FSError import *

class ProtectFlags:
  FIBF_DELETE = 1
  FIBF_EXECUTE = 2
  FIBF_WRITE = 4
  FIBF_READ = 8
  FIBF_ARCHIVE = 16
  FIBF_PURE = 32
  FIBF_SCRIPT = 64
  
  flag_txt = "HSPArwed"
  flag_num = len(flag_txt)
  flag_none = 0xf # --------
  empty_string = "-" * flag_num
  
  def __init__(self, mask=0):
    self.mask = mask
    
  def __str__(self):
    txt = ""
    pos = self.flag_num - 1
    m = 1 << pos
    for i in xrange(self.flag_num):
      bit = self.mask & m == m
      show = '-'
      flg = self.flag_txt[i]
      flg_low = flg.lower()
      if bit:
        if flg_low != flg:
          show = flg_low
      else:
        if flg_low == flg:
          show = flg_low
      txt += show
      m >>= 1
      pos -= 1
    return txt
    
  def bin_str(self):
    res = ""
    m = 1 << (self.flag_num - 1)
    for i in xrange(self.flag_num):
      if m & self.mask == m:
        res += "1"
      else:
        res += "0" 
      m >>= 1
    return res

  def short_str(self):
    return str(self).replace("-","")
    
  def parse(self, s):
    if len(s) == 0:
      return
    # allow to add with '+' or sub with '-'
    n = self.flag_txt
    mode = '+'
    self.mask = self.flag_none
    for a in s.lower():
      if a in '+-':
        mode = a
      else:
        mask = None   
        is_low = None
        for i in xrange(self.flag_num):
          flg = self.flag_txt[i]
          flg_low = flg.lower()
          if flg_low == a:
            mask = 1<<(self.flag_num - 1 - i)
            is_low = flg_low == flg
            break
        if mask == None:
          raise FSError(INVALID_PROTECT_FORMAT,extra="char: "+a)
        # apply mask
        if mode == '+':
          if is_low:
            self.mask &= ~mask
          else:
            self.mask |= mask
        else:
          if is_low:
            self.mask |= mask
          else:
            self.mask &= ~mask
  
  def is_set(self, mask):
    return self.mask & mask == 0 # LO active
  def set(self, mask):
    self.mask &= ~mask
  def clr(self, mask):
    self.mask |= mask

  def is_d(self):
    return self.is_set(self.FIBF_DELETE)
  def is_e(self):
    return self.is_set(self.FIBF_EXECUTE)
  def is_w(self):
    return self.is_set(self.FIBF_WRITE)
  def is_r(self):
    return self.is_set(self.FIBF_READ)

if __name__ == '__main__':
  inp = ["h","s","p","a","r","w","e","d"]
  for i in inp:
    p = ProtectFlags() 
    p.parse(i)
    s = str(p)
    if not i in s:
      print(s)

    