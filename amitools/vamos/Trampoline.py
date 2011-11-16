from Exceptions import *
from CPU import *

class Trampoline:
  
  def __init__(self, cpu, mem):
    self.code = []
    self.cpu = cpu
    self.mem = mem
    self.trap_addr = 0
  
  def init(self):
    self.code = []
    self.trap_addr = 0
  
  def done(self):
    self.write_code()
    self.setup_on_stack()
  
  def save_all(self):
    self.code.extend([0x48e7, 0xfffe]) # movem.l d0-d7/a0-a6,-(sp)
  
  def restore_all(self):
    self.code.extend([0x4cdf, 0x7fff]) # movem.l (sp)+,d0-d7/a0-a6
    
  def rts(self):
    self.code.append(0x4e75) # rts
  
  def trap(self, func):
    self.code.append(0x4e70) # reset = trap
    self.trap_func = func
  
  def set_dx_l(self, num, val):
    op = 0x203c # move.l #LONG, d0
    op += num * 0x200
    hi = (val >> 16) & 0xffff
    lo = val & 0xffff
    self.code.extend([op, hi, lo])
  
  def set_ax_l(self, num, val):
    op = 0x41f9 # lea.l LONG, a0
    op += num * 0x200
    hi = (val >> 16) & 0xffff
    lo = val & 0xffff
    self.code.extend([op, hi, lo])
  
  def jsr(self, addr):
    hi = (addr >> 16) & 0xffff
    lo = addr & 0xffff
    self.code.extend([0x4eb9, hi, lo]) # jsr LONG
  
  def get_code_size(self):
    return len(self.code) * 2
  
  def write_code(self):
    size = len(self.code) * 2
    if size > self.mem.size:
      raise VamosInternalError("Trampoline too small: want=%d got=%d" % (size, self.mem.size))
    addr = self.mem.addr
    for w in self.code:
      if w == 0x4e70:
        self.trap_addr = addr
      self.mem.access.write_mem(1, addr, w)
      addr += 2

  def setup_on_stack(self):
    old_stack = self.cpu.r_reg(REG_A7)
    new_stack = old_stack - 4
    self.cpu.w_reg(REG_A7, new_stack)
    self.mem.access.w32(new_stack, self.mem.addr)

