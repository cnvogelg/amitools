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
    self.name
  
  def get_name(self):
    return self.name
  
  def r_reg(self, reg, val):
    pass
  
  def w_reg(self, reg):
    return 0