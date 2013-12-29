# registers
REG_D0 = 0
REG_D1 = 1
REG_D2 = 2
REG_D3 = 3
REG_D4 = 4
REG_D5 = 5
REG_D6 = 6
REG_D7 = 7
REG_A0 = 8
REG_A1 = 9
REG_A2 = 10
REG_A3 = 11
REG_A4 = 12
REG_A5 = 13
REG_A6 = 14
REG_A7 = 15

class CPU:
  def __init__(self, name):
    self.name = name
  
  def get_name(self):
    return self.name
  
  def r_reg(self, reg):
    return 0
  def w_reg(self, reg, val):
    pass
  def r_pc(self):
    return 0
  def w_pc(self, val):
    pass
  def r_sr(self):
    return 0
  def w_sr(self, val):
    pass
  def pulse_reset(self):
    pass
  def execute(self, num_cycles):
    return 0
  def end(self):
    pass
  def trap_setup(self, func):
    return -1
  def trap_free(self, tid):
    pass

  sr_chars = "CVZNX"
  
  def sr_str(self, val):
    mask = 1
    res = []
    for c in self.sr_chars:
      if (val & mask) == mask:
        res.append(c)
      else:
        res.append('-')
      mask *= 2
    return "".join(res)
  
  def get_state(self):
    state = {
      'pc' : self.r_pc(),
      'sr' : self.r_sr(),
      'sr_str' : self.sr_str(self.r_sr()),
    }
    # data register
    dx = []
    state['dx'] = dx
    for i in xrange(8):
      dx.append(self.r_reg(i))
    # addr register
    ax = []
    state['ax'] = ax
    for i in xrange(8):
      ax.append(self.r_reg(8+i))
    return state
    
  def dump_state(self, state=None):
    if state == None:
      state = self.get_state()
    
    res = []
    res.append( "PC=%08x  SR=%s" % (state['pc'],state['sr_str']))
    # data register
    dx = []
    pos = 0
    for d in state['dx']:
      dx.append("D%d=%08x" % (pos, d))
      pos += 1
    res.append( "  ".join(dx) )
    # addr register
    ax = []
    pos = 0
    for a in state['ax']:
      ax.append("A%d=%08x" % (pos, a))
      pos += 1
    res.append( "  ".join(ax))
    return res