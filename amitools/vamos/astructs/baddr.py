class BAddr(object):
  """represent an address in BCPL LONG notation"""
  def __init__(self, baddr=0):
    self.baddr = baddr
    self.addr = baddr << 2

  def __repr__(self):
    return "BAddr(%d)" % self.baddr

  def __str__(self):
    return "BAddr(%08x,addr=%08x)" % (self.baddr, self.addr)

  def __eq__(self, other):
    if isinstance(other, BAddr):
      return other.baddr == self.baddr
    elif type(other) is int:
      # int compares addr
      return other == self.addr
    else:
      return NotImplemented

  def __ne__(self, other):
    if isinstance(other, BAddr):
      return other.baddr != self.baddr
    elif type(other) is int:
      # int compares addr
      return other != self.addr
    else:
      return NotImplemented

  def __rshift__(self, other):
    # FIXME compat: BAddr() >> 2 == baddr
    if other == 2:
      return self.baddr
    else:
      return NotImplemented

  def __add__(self, other):
    # FIXME compat: BAddr() + off = addr
    if type(other) is int:
      return self.addr + other
    else:
      return NotImplemented

  def __and__(self, other):
    # FIXME compat: BAddr() & mask = addr
    if type(other) is int:
      return self.addr & other
    else:
      return NotImplemented

  def __int__(self):
    # auto convert to addr
    return self.addr

  @classmethod
  def from_addr(cls, addr):
    if addr & 3 != 0:
      raise ValueError("BAddr needs long word aligned address!")
    return cls(addr >> 2)

  def get_baddr(self):
    return self.baddr

  def get_addr(self):
    return self.addr
