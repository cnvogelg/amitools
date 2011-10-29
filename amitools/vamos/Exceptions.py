class VamosError(Exception):
  def __str__(self):
    return "VamosError"

class InvalidMemoryAccessError(VamosError):
  def __init__(self, access_type, width, addr, src):
    self.access_type = access_type
    self.width = width
    self.addr = addr
    self.src = src
  def __str__(self):
    return "Invalid Memory Access %s(%d): %06x [%s]" % (self.access_type,2**self.width,self.addr,self.src)

class OutOfAmigaMemoryError(VamosError):
  def __init__(self, alloc, size):
    self._alloc = alloc
    self._size = size
  def __str__(self):
    return "Out of Amiga Memory: %s size=%s" % (str(self._alloc), self._size)

class UnsupportedFeatureError(VamosError):
  def __init__(self, what):
    self._what = what
  def __str__(self):
    return "Unupported vamos Feature: %s" % self._what

class AmigaDeviceNotFoundError(VamosError):
  def __init__(self, dev):
    self._dev = dev
  def __str__(self):
    return "Amiga volume not found: %s" % self._dev

class VersionMismatchError(VamosError):
  def __init__(self, what, got, want):
    self._what = _what
    self._got = _got
    self._want = _want
  def __str__(self):
    return "Version Mismatch: %s got=%d want=%d" % (self._what, self._got, self._want)

class VamosInternalError(VamosError):
  def __init__(self, what):
    self._what = what
  def __str__(self):
    return "Internal Vamos Error: %s" % self._what
