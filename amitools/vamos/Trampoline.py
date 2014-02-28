from Exceptions import *
from CPU import *

from Log import log_tp

class Trampoline:
  
  def __init__(self, ctx, name):
    self.ctx = ctx
    self.cpu = ctx.cpu
    self.name = name
    self.mem = None

    self.code = [] # words for code
    self.data = [] # bytes for data
    self.traps = []
    self.label_pos = []
    self.labels = []
    self.data_addr = None
    self.final_func = None

  def done(self):
    """add final rts and generate trampoline in memory"""
    self._write_code()
    self._setup_on_stack()
    
  def set_label(self):
    """during trampoline definition set  a label you can later reference"""
    pos = len(self.label_pos)
    self.label_pos.append(len(self.code))
    return pos
  
  def get_label(self, pos):
    """after done() you can get the address of a label"""
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
  
  def final_rts(self, final_func=None):
    self.code.append(0xa001) # special token for cleanup trap and rts
    self.final_func = final_func

  def trap(self, func, auto_rts=False):
    self.code.append(0xa000) # a-line = trap
    self.traps.append((func,auto_rts))
  
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
  
  # ----- data commands (return offset) -----

  def dc_b(self, b):
    pos = len(self.data)
    self.data.append(b)
    return pos

  def dc_w(self, w):
    pos = len(self.data)
    hi = (w >> 8) & 0xff
    lo = w & 0xff
    self.data.extend([hi, lo])
    return pos

  def dc_l(self, l):
    pos = len(self.data)
    self.dc_w( (l >> 16) & 0xffff )
    self.dc_w( l & 0xffff )
    return pos

  # ----- after trampoline is created in mem you can patch it -----

  def patch_at_label_b(self, pos, offset, value):
    """patch memory at a label. write long"""
    addr = self.get_label(pos)
    self.mem.access.write_mem( 0, addr, value ) 

  def patch_at_label_w(self, pos, offset, value):
    """patch memory at a label. write long"""
    addr = self.get_label(pos)
    self.mem.access.write_mem( 1, addr, value ) 

  def patch_at_label_l(self, pos, offset, value):
    """patch memory at a label. write long"""
    addr = self.get_label(pos)
    self.mem.access.write_mem( 2, addr, value ) 

  def patch_b(self, pos, val):
    """patch data memory previously defined with dc.b"""
    self.mem.access.write_mem( 0, self.data_addr + pos, val )

  def patch_w(self, pos, val):
    """patch data memory previously defined with dc.w"""
    self.mem.access.write_mem( 1, self.data_addr + pos, val )

  def patch_l(self, pos, val):
    """patch data memory previously defined with dc.l"""
    self.mem.access.write_mem( 2, self.data_addr + pos, val )

  # ----- internals -----
  
  def _gen_trap_func(self, trap_func):
    """add a user defined trap function and surround it with logging"""
    def tf(op,pc):
      log_tp.debug("#%s { trap: %s",self.name, trap_func.__name__)
      trap_func()
      log_tp.debug("#%s } trap: %s",self.name, trap_func.__name__)
    return tf
  
  def _gen_trap_cleanup(self, mem):
    """clean up function that removes trap memory on final_rts"""
    def tf(op,pc):
      log_tp.debug("#%s: cleaning up", self.name)
      if self.final_func != None:
        self.final_func()
      self.ctx.alloc.free_memory(mem)
    return tf

  def _write_code(self):
    # calc and allocate memory
    size = len(self.code) * 2 + len(self.data)
    self.mem = self.ctx.alloc.alloc_memory(self.name, size)
    log_tp.debug("#%s: allocating %d bytes", self.name, size)

    # now fill in code
    addr = self.mem.addr
    trap_pos = 0
    code_pos = 0
    for w in self.code:
      # handle trap -> register one shot at run time
      if w == 0xa000 or w == 0xa001:
        # final trap for clean up and rts
        if w == 0xa001:
          tf = self._gen_trap_cleanup(self.mem)
          auto_rts = True
        # normal trap
        else:
          trap_func,auto_rts = self.traps[trap_pos]
          tf = self._gen_trap_func(trap_func)
          trap_pos += 1
        code = self.ctx.cpu.trap_setup(tf, one_shot=True, auto_rts=auto_rts)
        if code == -1:
          raise VamosInternalError("No more traps for trampoline left!")
        self.mem.access.write_mem(1, addr, 0xa000 | code)
      else:
        self.mem.access.write_mem(1, addr, w)
      # check for label
      if code_pos in self.label_pos:
        self.labels.append(addr)
      code_pos += 1
      addr += 2

    # now write data
    self.data_addr = addr
    for b in self.data:
      self.mem.access.write_mem(0, addr, b)
      addr += 1

  def _setup_on_stack(self):
    old_stack = self.cpu.r_reg(REG_A7)
    new_stack = old_stack - 4
    self.cpu.w_reg(REG_A7, new_stack)
    self.ctx.mem.access.w32(new_stack, self.mem.addr)

