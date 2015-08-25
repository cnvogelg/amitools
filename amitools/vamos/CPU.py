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
REG_PC = 16

class CPUState:
  def __init__(self):
    self.pc = None
    self.sr = None
    self.dx = None
    self.ax = None

  sr_chars = "CVZNX"

  def _sr_str(self, val):
    mask = 1
    res = []
    for c in self.sr_chars:
      if (val & mask) == mask:
        res.append(c)
      else:
        res.append('-')
      mask *= 2
    return "".join(res)

  def get(self, cpu):
    self.pc = cpu.r_pc()
    self.sr = cpu.r_sr()
    # data register
    dx = []
    self.dx = dx
    for i in xrange(8):
      dx.append(cpu.r_reg(i))
    # addr register
    ax = []
    self.ax = ax
    for i in xrange(8):
      ax.append(cpu.r_reg(8+i))

  def dump(self):
    res = []
    res.append( "PC=%08x  SR=%s" % (self.pc, self._sr_str(self.sr)))
    # data register
    dx = []
    pos = 0
    for d in self.dx:
      dx.append("D%d=%08x" % (pos, d))
      pos += 1
    res.append( "  ".join(dx) )
    # addr register
    ax = []
    pos = 0
    for a in self.ax:
      ax.append("A%d=%08x" % (pos, a))
      pos += 1
    res.append( "  ".join(ax))
    return res
