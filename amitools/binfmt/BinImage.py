
SEGMENT_TYPE_CODE = 0
SEGMENT_TYPE_DATA = 1
SEGMENT_TYPE_BSS = 2

SEGMENT_FLAG_READ_ONLY = 1

segment_type_names = [
  "CODE", "DATA", "BSS"
]


class Relocations:
  def __init__(self, to_seg):
    self.to_seg = to_seg
    self.entries = []

  def add_reloc(self, offset, width=2):
    self.entries.append((offset, width))

  def get_relocs(self):
    return self.entries


class SymbolTable:
  def __init__(self):
    self.symbols = []

  def add_symbol(self, offset, name):
    self.symbols.append((offset, name))


class Segment:
  def __init__(self, seg_type, size, data=None, flags=None):
    self.seg_type = seg_type
    self.size = size
    self.data = data
    self.flags = flags
    self.relocs = {}
    self.symtab = None
    self.id = None
    self.file_data = None

  def __str__(self):
    relocs = []
    for to_seg in self.relocs:
      r = self.relocs[to_seg]
      relocs.append("(#%d:size=%d)" % (to_seg.id, len(r.entries)))
    if self.symtab is not None:
      symtab = "symtab=#%d" % len(self.symtab.symbols)
    else:
      symtab = ""
    return "[#%d:%s:size=%d,flags=%d,%s,%s]" % (self.id,
      segment_type_names[self.seg_type], self.size, self.flags,
      ",".join(relocs), symtab)

  def get_type(self):
    return self.seg_type

  def get_size(self):
    return self.size

  def get_data(self):
    return self.data

  def add_reloc(self, to_seg, relocs):
    self.relocs[to_seg] = relocs

  def set_symtab(self, symtab):
    self.symtab = symtab

  def get_symtab(self):
    return self.symtab

  def set_file_data(self, file_data):
    """set associated loaded binary file"""
    self.file_data = file_data

  def get_file_data(self):
    """get associated loaded binary file"""
    return self.file_data


class BinImage:
  """A binary image contains all the segments of a program's binary image.
  """
  def __init__(self):
    self.segments = []
    self.file_data = None

  def __str__(self):
    return "<%s>" % ",".join(map(str,self.segments))

  def add_segment(self, seg):
    seg.id = len(self.segments)
    self.segments.append(seg)

  def get_segments(self):
    return self.segments

  def set_file_data(self, file_data):
    """set associated loaded binary file"""
    self.file_data = file_data

  def get_file_data(self):
    """get associated loaded binary file"""
    return self.file_data

