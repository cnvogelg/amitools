from .mockcpu import MockCPU
from .mockmem import MockMemory
from .mocktraps import MockTraps

class MockMachine(object):
  def __init__(self, size_kib=16, fill=0):
    self.cpu = MockCPU()
    self.mem = MockMemory(size_kib, fill)
    self.traps = MockTraps()

  def get_cpu(self):
    return self.cpu

  def get_mem(self):
    return self.mem

  def get_traps(self):
    return self.traps
