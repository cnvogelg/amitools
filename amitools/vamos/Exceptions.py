class InvalidMemoryAccessError(Exception):
  def __init__(self, access_type, width, addr, src):
    self.access_type = access_type
    self.width = width
    self.addr = addr
    self.src = src
  def __str__(self):
    return "Invalid Memory Access %s(%d): %06x [%s]" % (self.access_type,2**self.width,self.addr,self.src)

class OutOfAmigaMemoryError(Exception):
  def __init__(self, alloc, size):
    self._alloc = alloc
    self._size = size
  def __str__(self):
    return "%s size=%s" % (str(self._alloc), self._size)
