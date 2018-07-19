class CString(object):
  """Manage C-Strings (with zero termination) in Amiga memory.

  The string is immutable as changing strings typically requires
  re-allocating memory for it.
  """

  def __init__(self, mem, addr, alloc=None, mem_obj=None, max_size=None):
    self.mem = mem
    self.addr = addr
    self.alloc = alloc
    self.mem_obj = mem_obj
    self.max_size = max_size

  def __str__(self):
    return self.get_string()

  def __int__(self):
    return self.addr

  def __repr__(self):
    return "CString(@%06x:%s)" % (self.addr, self.get_string())

  def __eq__(self, other):
    if type(other) is int:
      return self.addr == other
    elif type(other) is str:
      return self.get_string() == other
    elif isinstance(other, CString):
      return self.addr == other.addr
    else:
      return NotImplemented

  def get_mem(self):
    return self.mem

  def get_addr(self):
    return self.addr

  def get_string(self):
    if self.addr == 0:
      return None
    else:
      return self.mem.r_cstr(self.addr)

  def get_max_size(self):
    return self.max_size

  def get_size(self):
    return len(self.get_string())

  def set_string(self, txt):
    if self.max_size:
      if len(txt) > self.max_size:
        raise ValueError("new string too long!")
    if self.addr == 0:
      raise ValueError("cstr is NULL")
    else:
      self.mem.w_cstr(self.addr, txt)

  def free(self):
    if self.alloc:
      self.alloc.free_cstr(self.mem_obj)
      self.mem_obj = None
      self.alloc = None
      self.addr = 0
      self.max_size = 0

  @staticmethod
  def alloc(alloc, txt, tag=None):
    """allocate memory for the given txt with the allocator

    Returns a CString object with allocation info.
    You can free() the object later on
    """
    if type(txt) is CString:
      return txt
    if tag is None:
      tag = "CString('%s')" % txt
    mem = alloc.get_mem()
    # NULL ptr
    if txt is None:
      mem_obj = None
      alloc = None
      addr = 0
      n = 0
    # valid string
    else:
      mem_obj = alloc.alloc_cstr(tag, txt)
      addr = mem_obj.addr
      n = len(txt)
    return CString(mem, addr, alloc, mem_obj, n)
