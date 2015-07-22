from __future__ import print_function
import struct


class HunkDebugLineEntry:
  def __init__(self, offset, src_line):
    self.offset = offset
    self.src_line = src_line

  def __str__(self):
    return "[+%08x: %d]" % (self.offset, self.src_line)

  def get_offset(self):
    return self.offset

  def get_src_line(self):
    return self.src_line


class HunkDebugLine:
  """structure to hold source line info"""
  def __init__(self, tag, src_file, base_offset):
    self.tag = tag
    self.src_file = src_file
    self.base_offset = base_offset
    self.entries = []

  def add_entry(self, offset, src_line):
    self.entries.append(HunkDebugLineEntry(offset, src_line))

  def __str__(self):
    prefix = "{%s,%s,@%08x:" % (self.tag, self.src_file, self.base_offset)
    return prefix + ",".join(map(str,self.entries)) + "}"

  def get_src_file(self):
    return self.src_file

  def get_base_offset(self):
    return self.base_offset

  def get_entries(self):
    return self.entries


class HunkDebug:
  def decode(self, debug_data):
    """decode a data block from a debug hunk"""
    if len(debug_data) < 12:
      return None
    # +4: tag
    tag = debug_data[4:8]
    if tag == 'LINE': # SAS/C source line info
      # +0: base_offset for file
      base_offset = self._read_long(debug_data, 0)
      # +8: string file name
      src_file, src_size = self._read_string(debug_data, 8)
      dl = HunkDebugLine(tag, src_file, base_offset)
      off = 12 + src_size
      num = (len(debug_data) - off) / 8
      for i in range(num):
        src_line = self._read_long(debug_data, off)
        offset = self._read_long(debug_data, off+4)
        off += 8
        dl.add_entry(offset, src_line)
      return dl
    else:
      return None

  def _read_string(self, buf, pos):
    size = self._read_long(buf,pos) * 4
    off = pos + 4
    data = buf[off:off+size]
    pos = data.find('\0')
    if pos == 0:
      return "", size
    elif pos != -1:
      return data[:pos], size
    else:
      return data, size

  def _read_long(self, buf, pos):
    return struct.unpack(">I",buf[pos:pos+4])[0]


# ----- mini test -----
if __name__ == '__main__':
  import sys
  from HunkBlockFile import HunkBlockFile, HunkDebugBlock
  hd = HunkDebug()
  for a in sys.argv[1:]:
    hbf = HunkBlockFile()
    hbf.read_path(a)
    for blk in hbf.get_blocks():
      if isinstance(blk, HunkDebugBlock):
        dd = hd.decode(blk.debug_data)
        print(a,"->",dd)
