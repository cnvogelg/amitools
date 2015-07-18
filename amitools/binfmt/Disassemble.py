from amitools.util.DisAsm import DisAsm
from BinImage import *

class Disassemble:
  """allows to disassemble code segments of a BinImage"""
  def __init__(self, use_objdump=False, cpu='68000'):
    self.disasm = DisAsm(use_objdump, cpu)

  def _find_symbol(self, segment, addr):
    symtab = segment.get_symtab()
    if symtab is None:
      return None
    for symbol in symtab.get_symbols():
      off = symbol.get_offset()
      if off == addr:
        return symbol.get_name()
    return None

  def _get_reloc(self, segment, addr, size):
    to_segs = seg.get_reloc_to_segs()
    for to_seg in to_segs:
      reloc = seg.get_reloc(to_seg)
      for r in reloc.get_relocs():
        off = r.get_offset()
        if off >= addr and off <= (addr + size):
          return r,to_seg,off
    return None

  def _get_line_info(self, segment, addr, size):
    r = self._get_reloc(segment, addr, size)
    if r is not None:
      delta = r[2] - addr
      return "; reloc +%02d: (#%02d + %08x)" % (delta, r[1].id, r[0].addend)
    return None

  def disassemble(self, segment, bin_img):
    # make sure its a code segment
    if segment.seg_type != SEGMENT_TYPE_CODE:
      return None

    # generate raw assembly
    data = segment.data
    lines = self.disasm.disassemble(data)

    # process lines
    result = []
    for l in lines:
      addr = l[0]
      word = l[1]
      code = l[2]

      # try to find a symbol for this addr
      symbol = self._find_symbol(segment, addr)
      if symbol is not None:
        line = "\t\t\t\t%s:" % symbol
        result.append(line)

      # create line info
      size = len(word) * 2
      info = self._get_line_info(segment, addr, size)
      if info is None:
        info = ""

      # create final line
      line = "%08x\t%-20s\t%-30s %s" % (addr," ".join(map(lambda x: "%04x" %x, word)),code,info)
      result.append(line)

    return result

# mini test
if __name__ == '__main__':
  import sys
  from BinFmt import BinFmt
  bf = BinFmt()
  for a in sys.argv[1:]:
    bi = bf.load_image(a)
    if bi is not None:
      print(a)
      d = Disassemble()
      for seg in bi.get_segments():
        if seg.seg_type == SEGMENT_TYPE_CODE:
          lines = d.disassemble(seg, bi)
          for l in lines:
            print(l)
