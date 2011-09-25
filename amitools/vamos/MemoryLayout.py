
MEMORY_WIDTH_BYTE = 0
MEMORY_WIDTH_WORD = 1
MEMORY_WIDTH_LONG = 2

class InvalidMemoryAccessError(Exception):
  def __init__(self, width, addr):
    self.width = width;
    self.addr = addr
  def __str__(self):
    return "Invalid Memory Access (width=%d, addr=%06x)" % (self.width,self.addr)

class MemoryLayout:
  
  def __init__(self, verbose=False):
    self.ranges = []
    self.verbose = verbose
    
  def add_range(self, range):
    self.ranges.append(range)
  
  def remove_range(self, range):
    self.ranges.remove(range)
  
  def get_read_funcs(self):
    return ( lambda addr: self.read_mem(0,addr),
             lambda addr: self.read_mem(1,addr),
             lambda addr: self.read_mem(2,addr))
  
  def get_write_funcs(self):
    return ( lambda addr,val: self.write_mem(0,addr,val),
             lambda addr,val: self.write_mem(1,addr,val),
             lambda addr,val: self.write_mem(2,addr,val))
  
  def read_mem(self, width, addr):
    for r in self.ranges:
      if r.is_inside(addr):
        val = r.read_mem(width, addr)
        if self.verbose:
          print "R(%d): %06x: %x (%s)" % (2**width, addr, val, r.name)
        return val
    raise InvalidMemoryAccessError(width, addr)
  
  def write_mem(self, width, addr, val):
    for r in self.ranges:
      if r.is_inside(addr):
        r.write_mem(width, addr, val)
        if self.verbose:
          print "W(%d): %06x: %x (%s)" % (2**width, addr, val, r.name)
        return None
    raise InvalidMemoryAccessError(width, addr)
