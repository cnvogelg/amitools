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
    self.data = [] #
    self.code_size = 0
    self.data_size = 0
    self.code_addr = None
    self.data_addr = None
    self.trapcode  = None

  def done(self):
    """add final rts and generate trampoline in memory"""
    self._generate()
    self._setup_on_stack()

  def get_code_offset(self):
    """before done() you can get the current code offset"""
    return self.code_size

  def get_code_addr(self, offset):
    """after done() you can query the absolute address of an offset"""
    return self.code_addr + offset

  # ----- trampoline commands -----

  def save_all(self):
    self.code.extend([0x48e7, 0xfffe]) # movem.l d0-d7/a0-a6,-(sp)
    self.code_size += 4

  def restore_all(self):
    self.code.extend([0x4cdf, 0x7fff]) # movem.l (sp)+,d0-d7/a0-a6
    self.code_size += 4

  def save_all_but_d0(self):
    self.code.extend([0x48e7, 0x7ffe]) # movem.l d1-d7/a0-a6,-(sp)
    self.code_size += 4

  def restore_all_but_d0(self):
    self.code.extend([0x4cdf, 0x7ffe]) # movem.l (sp)+,d1-d7/a0-a6
    self.code_size += 4

  def rts(self):
    self.code.append(0x4e75) # rts
    self.code_size += 2

  def final_rts(self, final_func=None):
    self.code.append(('trap',final_func,True,True))
    self.code_size += 2 # a-line opcode

  def trap(self, func, auto_rts=False):
    self.code.append(('trap',func,auto_rts,False))
    self.code_size += 2 # a-line opcode

  def set_dx_l(self, num, val):
    op = 0x203c # move.l #LONG, d0
    op += num * 0x200
    hi = (val >> 16) & 0xffff
    lo = val & 0xffff
    self.code.extend([op, hi, lo])
    self.code_size += 6

  def set_ax_l(self, num, val):
    op = 0x41f9 # lea.l LONG, a0
    op += num * 0x200
    hi = (val >> 16) & 0xffff
    lo = val & 0xffff
    self.code.extend([op, hi, lo])
    self.code_size += 6

  def jsr(self, addr):
    hi = (addr >> 16) & 0xffff
    lo = addr & 0xffff
    self.code.extend([0x4eb9, hi, lo]) # jsr LONG
    self.code_size += 6

  def jmp(self, addr):
    hi = (addr >> 16) & 0xffff
    lo = addr & 0xffff
    self.code.extend([0x4ef9, hi, lo]) # jmp LONG
    self.code_size += 6

  def write_ax_l(self, num, addr, is_data_offset=False):
    op = 0x23c8 # move.l ax, addr.l
    op += num
    hi = (addr >> 16) & 0xffff
    lo = addr & 0xffff
    if is_data_offset:
      self.code.extend([op, ('data_offset',addr)])
    else:
      self.code.extend([op, hi, lo])
    self.code_size += 6

  def read_ax_l(self, num, addr, is_data_offset=False):
    op = 0x2079 # movea.l addr.l, ax
    op += num * 0x200
    hi = (addr >> 16) & 0xffff
    lo = addr & 0xffff
    if is_data_offset:
      self.code.extend([op, ('data_offset',addr)])
    else:
      self.code.extend([op, hi, lo])
    self.code_size += 6

  # ----- data commands (return offset) -----

  def dc_b(self, b):
    """reserve a data byte and return data offset"""
    pos = self.data_size
    self.data.append((0,b))
    self.data_size += 1
    return pos

  def dc_w(self, w):
    """reserve a data word and return data offset"""
    pos = self.data_size
    self.data.append((1,w))
    self.data_size += 2
    return pos

  def dc_l(self, l):
    """reserve a data long and return data offset"""
    pos = self.data_size
    self.data.append((2,l))
    self.data_size += 4
    return pos

  # ----- modify an existing trampoline at an offset

  def modify_long(self,offset,data):
    self.mem.access.w16(self.code_addr + offset + 2,(data >> 16) & 0xffff)
    self.mem.access.w16(self.code_addr + offset + 4,data         & 0xffff)
  
  # ----- internals -----

  def _gen_trap_func(self, trap_func):
    """add a user defined trap function and surround it with logging"""
    def tf(op,pc):
      log_tp.debug("#%s { trap: %s",self.name, trap_func.__name__)
      trap_func()
      log_tp.debug("#%s } trap: %s",self.name, trap_func.__name__)
    return tf

  def _gen_trap_cleanup(self, mem, trap_func):
    """clean up function that removes trap memory on final_rts"""
    def tf(op,pc):
      log_tp.debug("#%s: cleaning up", self.name)
      if trap_func != None:
        trap_func()
      self.ctx.alloc.free_memory(mem)
    return tf

  def _gen_trap(self, addr, opts):
    """generate a trap in memory"""
    func, auto_rts, final = opts
    # final trap with cleanup func
    if final:
      tf = self._gen_trap_cleanup(self.mem, func)
    # normal trap
    else:
      tf = self._gen_trap_func(func)
    # create a trap
    code = self.ctx.traps.setup(tf, one_shot=True, auto_rts=auto_rts)
    if code == -1:
      raise VamosInternalError("No more traps for trampoline left!")
    # place trap opcode
    self.trapcode = code
    opcode = 0xa000 | code
    self.mem.access.w16(addr, opcode)
    if final:
      log_tp.debug("#%s: final trap: opcode=%04x @%08x", self.name, opcode, addr)

  def _generate(self):
    # calc and allocate memory
    size = self.code_size + self.data_size
    self.mem = self.ctx.alloc.alloc_memory(self.name, size)
    addr = self.mem.addr
    log_tp.debug("#%s: @%06x: allocating %d bytes (code=%d, data=%d)",
      self.name, addr, size, self.code_size, self.data_size)

    # abs addresses of code and data
    self.code_addr = addr
    self.data_addr = addr + self.code_size

    # now fill in code
    for w in self.code:
      # === special 'opcode' ===
      if type(w) == tuple:
        special = w[0]
        # --- a trap ---
        if special == 'trap':
          self._gen_trap(addr, w[1:])
          addr += 2
        # --- data offset ---
        elif special == 'data_offset':
          offset = w[1]
          data_addr = self.data_addr + offset
          self.mem.access.w32(addr, data_addr)
          addr += 4
        # --- unknown special ---
        else:
          raise VamosInternalError("Invalid special: %s" % special)
      # === normal code word ===
      else:
        self.mem.access.w16(addr, w)
        addr += 2

    # now write data
    for b in self.data:
      width,val = b
      self.mem.access.write_mem(width, addr, val)
      addr += 2**width

  def _setup_on_stack(self):
    old_stack = self.cpu.r_reg(REG_A7)
    new_stack = old_stack - 4
    self.cpu.w_reg(REG_A7, new_stack)
    self.ctx.mem.access.w32(new_stack, self.mem.addr)

