from Exceptions import *
from CPU import *

from Log import log_tp

class Trampoline:
  
  def __init__(self, ctx, mem):
    self.code = []
    self.ctx = ctx
    self.cpu = ctx.cpu
    self.mem = mem
    self.traps = []
    self.label_pos = []
    self.labels = []
  
  def init(self):
    self.code = []
    self.traps = []
    self.label_pos = []
    self.labels = []
  
  def done(self):
    self._write_code()
    self._setup_on_stack()
    
  def set_label(self):
    pos = len(self.label_pos)
    self.label_pos.append(len(self.code))
    return pos
  
  def get_label(self, pos):
    return self.labels[pos]
  
  # ----- trampoline commands -----
  
  def save_all(self):
    self.code.extend([0x48e7, 0xfffe]) # movem.l d0-d7/a0-a6,-(sp)
  
  def restore_all(self):
    self.code.extend([0x4cdf, 0x7fff]) # movem.l (sp)+,d0-d7/a0-a6
    
  def save_all_but_d0(self):
    self.code.extend([0x48e7, 0x7ffe]) # movem.l d1-d7/a0-a6,-(sp)

  def restore_all_but_d0(self):
    self.code.extend([0x4cdf, 0x7ffe]) # movem.l (sp)+,d1-d7/a0-a6

  def rts(self):
    self.code.append(0x4e75) # rts
  
  def trap(self, func):
    self.code.append(0x4e70) # reset = trap
    self.traps.append(func)
  
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

  def jmp(self, addr):
    hi = (addr >> 16) & 0xffff
    lo = addr & 0xffff
    self.code.extend([0x4ef9, hi, lo]) # jmp LONG
  
  def write_ax_l(self, num, addr):
    op = 0x23c8 # move.l ax, addr.l
    op += num
    hi = (addr >> 16) & 0xffff
    lo = addr & 0xffff
    self.code.extend([op, hi, lo])
    
  def read_ax_l(self, num, addr):
    op = 0x2079 # movea.l addr.l, ax
    op += num * 0x200
    hi = (addr >> 16) & 0xffff
    lo = addr & 0xffff
    self.code.extend([op, hi, lo])      
    
  # ----- internals -----
  
  def _gen_trap_func(self, trap_func):
    def tf(op,pc):
      log_tp.debug("{ trap: %s",trap_func.__name__)
      trap_func()
      log_tp.debug("} trap: %s",trap_func.__name__)
    return tf
  
  def _write_code(self):
    size = len(self.code) * 2
    if size > self.mem.size:
      raise VamosInternalError("Trampoline too small: want=%d got=%d" % (size, self.mem.size))
    addr = self.mem.addr
    trap_pos = 0
    code_pos = 0
    for w in self.code:
      self.mem.access.write_mem(1, addr, w)
      # handle trap -> register one shot at run time
      if w == 0x4e70:
        trap_func = self.traps[trap_pos]
        tf = self._gen_trap_func(trap_func)
        code = self.ctx.cpu.trap_setup(tf, one_shot=True)
        if code == -1:
          raise VamosInternalError("No more traps for trampoline left!")
        self.mem.access.write_mem(1, addr, 0xa000 | code)
        trap_pos += 1
      # check for label
      if code_pos in self.label_pos:
        self.labels.append(addr)
      code_pos += 1
      addr += 2

  def _setup_on_stack(self):
    old_stack = self.cpu.r_reg(REG_A7)
    new_stack = old_stack - 4
    self.cpu.w_reg(REG_A7, new_stack)
    self.ctx.mem.access.w32(new_stack, self.mem.addr)

