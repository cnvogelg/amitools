from amitools.vamos.CPU import *
from amitools.vamos.machine import MockCPU

def machine_mockcpu_test():
  cpu = MockCPU()
  cpu.w_reg(REG_D0, 0xdeadbeef)
  assert cpu.r_reg(REG_D0) == 0xdeadbeef
  cpu.w_reg(REG_A6, 0xcafebabe)
  assert cpu.r_reg(REG_A6) == 0xcafebabe
  cpu.w_pc(0x123456)
  assert cpu.r_pc() == 0x123456
  cpu.w_sr(0x4711)
  assert cpu.r_sr() == 0x4711
