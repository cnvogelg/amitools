from LabelRange import LabelRange

class LabelSegment(LabelRange):
  def __init__(self, name, addr, size, segment):
    LabelRange.__init__(self, name, addr, size)
    self.segment = segment

  def get_symbol(self, addr):
    return self.segment.find_symbol(addr - self.addr)

  def get_src_line(self, addr):
    return self.segment.find_debug_line(addr - self.addr)

  def get_src_info(self, addr):
    info = self.get_src_line(addr)
    if info is None:
      return None
    f = info.get_file()
    src_file = f.get_src_file()
    src_line = info.get_src_line()
    return "[%s:%d]" % (src_file, src_line)
