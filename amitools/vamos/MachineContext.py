class MachineContext:
  def __init__(self, cpu, mem):
    self.cpu = cpu
    self.mem = mem
  
  def get_cpu(self):
    return self.cpu
  
  def get_mem(self):
    return self.mem
