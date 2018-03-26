class Segment:
  def __init__(self, name, addr, size, label, bin_img_seg):
    self.name = name
    self.addr = addr
    self.start = addr + 8
    self.size = size
    self.end = addr + size
    self.label = label
    self.bin_img_seg = bin_img_seg

  def get_name(self):
    return self.name

  def get_addr(self):
    return self.addr

  def get_start(self):
    return self.start

  def get_size(self):
    return self.size

  def get_end(self):
    return self.end

  def __str__(self):
    return "[Seg:'%s':%06x-%06x]" % (self.name, self.addr, self.end)


class SegList:
  def __init__(self, sys_bin_file, bin_img):
    self.sys_bin_file = sys_bin_file
    self.bin_img = bin_img
    self.segments = []
    self.b_addr = 0
    self.prog_start = 0
    self.size = 0
    self.usage = 1

  def add(self, segment):
    if len(self.segments) == 0:
      self.b_addr = (segment.addr+4) >> 2  # baddr of 'next' ptr
      self.prog_start = segment.addr + 8  # begin of first code segment
    self.segments.append(segment)
    self.size += segment.size

  def get_segment(self, num_seg):
    return self.segments[num_seg]

  def get_total_size(self):
    return self.size

  def __str__(self):
    return "[SegList:ami='%s':sys='%s':b_addr=%06x," \
        "prog=%06x,segs=#%d,size=%d,usage=%d]" % \
        (self.sys_bin_file, self.b_addr,
           self.prog_start, len(self.segments), self.size, self.usage)
