class Trampoline:
  
  def __init__(self):
    self.code = []
    
  def save_all(self):
    self.code.extend([0x48e7, 0xfffe]) # movem.l d0-d7/a0-a6,-(sp)
  
  def restore_all(self):
    self.code.extend([0x4cdf, 0x7fff]) # movem.l (sp)+,d0-d7/a0-a6
    
  def rts(self):
    self.code.append(0x4e75) # rts
  
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
  
  def write_code(self, mem, addr=-1):
    if addr == -1:
      addr = mem.addr
    for w in self.code:
      mem.write_mem(1, addr, w)
      addr += 2
