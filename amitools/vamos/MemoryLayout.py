from MemoryRange import MemoryRange
from Exceptions import InvalidMemoryAccessError

MEMORY_WIDTH_BYTE = 0
MEMORY_WIDTH_WORD = 1
MEMORY_WIDTH_LONG = 2

class MemoryLayout(MemoryRange):
  
  def __init__(self, name, addr, size, verbose=False):
    MemoryRange.__init__(self, name, addr, size)
    self.verbose = verbose
    self.ranges = []
    self.invalid_reads = []
    self.invalid_writes = []
    
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
  
  def get_range(self, addr):
    for r in self.ranges:
      if r.is_inside(addr):
        return r
    return None

  def read_mem(self, width, addr):
    try:
      r = self.get_range(addr)
      if r != None:
        val = r.read_mem(width, addr)
        if self.verbose:
          print "R(%d): %06x: %x (%s)" % (2**width, addr, val, r.name)
        return val
      else:
        raise InvalidMemoryAccessError(width, addr)
    except InvalidMemoryAccessError as e:
      print "R(%d): %06x !!!" % (e.width,e.addr)
      self.invalid_reads.append((e.width, e.addr))
      return 0
  
  def write_mem(self, width, addr, val):
    try:
      r = self.get_range(addr)
      if r != None:
        if self.verbose:
          print "W(%d): %06x: %x (%s)" % (2**width, addr, val, r.name)
        r.write_mem(width, addr, val)
        return None
      else:
        raise InvalidMemoryAccessError(width, addr)
    except InvalidMemoryAccessError as e:
      print "W(%d): %06x !!!" % (e.width, e.addr) 
      self.invalid_writes.append((e.width, e.addr))
      return None
    
  def write_data(self, addr, data):
    r = self.get_range(addr)
    if r != None:
      r.write_data(addr, data)
    else:
      raise InvalidMemoryAccessError(0, addr)

  def read_data(self, addr, size):
    r = self.get_range(addr)
    if r != None:
      return r.read_data(addr, size)
    else:
      raise InvalidMemoryAccessError(0, addr)

  def read_cstring(self, addr):
    r = self.get_range(addr)
    if r != None:
      return r.read_cstring(addr)
    else:
      raise InvalidMemoryAccessError(0, addr)
