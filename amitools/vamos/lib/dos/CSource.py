from DosStruct import CSourceDef

class CSource:
  """Simulate the AmigaDOS csource interface"""
  def __init__(self, buf=None):
    self.buf = buf
    if buf is not None:
      self.len = len(buf)
    else:
      self.len = 0
    self.pos = 0

  def getc(self):
    """return a character or None if EOF"""
    if self.buf is None:
      return EOF
    if self.pos < self.len:
      c = self.buf[self.pos]
      self.pos += 1
      return c
    else:
      return None

  def ungetc(self):
    """stuff back last character"""
    if self.pos > 0:
      self.pos -= 1

  def read_s(self, alloc, ptr):
    """read structure from Amiga memory"""
    c = alloc.map_struct("CSource", ptr, CSourceDef)
    buf_ptr = c.access.r_s('CS_Buffer')
    self.len = c.access.r_s('CS_Length')
    self.buf = bytes(alloc.access.r_data(buf_ptr, self.len))
    self.pos = c.access.r_s('CS_CurChr')

  def update_s(self, alloc, ptr):
    """update current pointer only"""
    c = alloc.map_struct("CSource", ptr, CSourceDef)
    c.access.w_s('CS_CurChr', self.pos)


class FileCSource:
  """wrap a file handle"""
  def __init__(self, fh):
    self.fh = fh
    self.last_ch = None

  def getc(self):
    if self.fh is None:
      return None
    ch = self.fh.getc()
    if ch == -1:
      self.last_ch = None
      return None
    else:
      self.last_ch = ch
      return chr(ch)

  def ungetc(self):
    if self.last_ch is not None:
      self.fh.ungetc(self.last_ch)
