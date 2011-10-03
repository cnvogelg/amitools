class InvalidMemoryAccessError(Exception):
  def __init__(self, width, addr):
    self.width = width;
    self.addr = addr
  def __str__(self):
    return "Invalid Memory Access (width=%d, addr=%06x)" % (self.width,self.addr)

class OutOfAmigaMemoryError(Exception):
  def __init__(self, alloc, size):
    self._alloc = alloc
    self._size = size
  def __str__(self):
    return "%s size=%s" % (str(self._alloc), self._size)
