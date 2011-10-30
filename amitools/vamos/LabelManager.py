from Exceptions import InvalidMemoryAccessError

MEMORY_WIDTH_BYTE = 0
MEMORY_WIDTH_WORD = 1
MEMORY_WIDTH_LONG = 2

class LabelManager:
  
  def __init__(self):
    self.ranges = []
  
  def add_label(self, range):
    self.ranges.append(range)
  
  def remove_label(self, range):
    self.ranges.remove(range)
  
  def get_all_labels(self):
    return self.ranges[:]
  
  def dump(self):
    for r in self.ranges:
      print r
  
  def get_label(self, addr):
    for r in self.ranges:
      if r.is_inside(addr):
        return r
    return None

  def get_label_offset(self, addr):
    r = self.get_label(addr)
    if r == None:
      return (None, 0)
    else:
      off = addr - r.addr
      return (r, off)

  def trace_mem(self, mode, width, addr, val):
    r = self.get_label(addr)
    if r != None:
      r.trace_mem(mode, width, addr, val)
    else:
      raise InvalidMemoryAccessError(mode, width, addr, 'main')
