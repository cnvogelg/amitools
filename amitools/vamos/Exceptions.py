class InvalidMemoryAccessError(Exception):
  def __init__(self, width, addr):
    self.width = width;
    self.addr = addr
  def __str__(self):
    return "Invalid Memory Access (width=%d, addr=%06x)" % (self.width,self.addr)

class OutOfAmigaMemoryError(Exception):
  def __init__(self, alloc):
    self._alloc = alloc
  def __str__(self):
    return str(self._alloc)
