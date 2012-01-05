from FSError import *

pf_empty_string = "-------"

class ProtectFlags:
  FIBF_DELETE = 1
  FIBF_EXECUTE = 2
  FIBF_WRITE = 4
  FIBF_READ = 8
  FIBF_ARCHIVE = 16
  FIBF_PURE = 32
  FIBF_SCRIPT = 64
  
  flag_txt = "sparwed"
  flag_num = len(flag_txt)
  
  def __init__(self, mask=0):
    self.mask = mask
    
  def __str__(self):
    txt = ""
    val = 64
    for i in xrange(self.flag_num):
      if self.mask & val == val:
        txt += '-'
      else:
        txt += self.flag_txt[i]
      val >>= 1
    return txt
    
  def parse(self, s):
    if len(s) == 0:
      return
    # allow to add with '+' or sub with '-'
    n = self.flag_txt
    mode = '+'
    for a in s.lower():
      if a in '+-':
        mode = a
      else:
        mask = None   
        for i in xrange(self.flag_num):
          if self.flag_txt[i] == a:
            mask = 1<<(self.flag_num - 1 - i)
            break
        if mask == None:
          raise FSError(INVALID_PROTECT_FORMAT,extra="char: "+a)
        # apply mask
        if mode == '+':
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
