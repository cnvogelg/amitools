import array
import struct

from amitools import Hunk

class HunkRelocate:
  
  def __init__(self, hunk_file, verbose=False):
    self.hunk_file = hunk_file
    self.verbose = verbose
    
  def get_sizes(self):
    sizes = []
    for segment in self.hunk_file.segments:
      main_hunk = segment[0]
      size = main_hunk['size']
      sizes.append(size)
    return sizes
  
  def get_seq_addrs(self, base_addr, padding=0):
    sizes = self.get_sizes()
    addrs = []
    addr = base_addr
    for s in sizes:
      addrs.append(addr)
      addr += s + padding
    return addrs
  
  def get_total_size(self):
    total = 0
    for segment in self.hunk_file.segments:
      main_hunk = segment[0]
      total += main_hunk['size']
    return total
  
  def relocate_one_block(self, addr, padding=0):
    addrs = self.get_seq_addrs(addr,padding=padding)
    datas = self.relocate(addrs)
    result = []
    for d in datas:
      result.append(d)
      if padding > 0:
        result.append('\0' * padding)
    return "".join(result)
  
  def relocate(self, addr):
    datas = []
    for segment in self.hunk_file.segments:
      main_hunk = segment[0]
      hunk_no = main_hunk['hunk_no']
      if main_hunk.has_key('data'):
        data = array.array('B',main_hunk['data'])
      else: # bss
        data = array.array('B','\0' * main_hunk['size'])
      
      if self.verbose:
        print "#%02d @ %06x" % (hunk_no, addr[hunk_no])
      
      # find relocation hunks
      for hunk in segment[1:]:
        # abs reloc 32
        if hunk['type'] == Hunk.HUNK_ABSRELOC32:
          reloc = hunk['reloc']
          for hunk_num in reloc:
            # get address of other hunk
            hunk_addr = addr[hunk_num]
            offsets = reloc[hunk_num]
            for offset in offsets:
              self.relocate32(hunk_no,data,offset,hunk_addr)
        
      datas.append(data.tostring())
    return datas

  def relocate32(self, hunk_no, data, offset, hunk_addr):
    delta = self.read_long(data, offset)
    addr = hunk_addr + delta
    self.write_long(data, offset, addr)
    if self.verbose:
      print "#%02d + %06x: %06x (delta) + %06x (hunk_addr) -> %06x" % (hunk_no, offset, delta, hunk_addr, addr)
    
  def read_long(self, data, offset):
    bytes = data[offset:offset+4]
    return struct.unpack(">I",bytes)[0]
  
  def write_long(self, data, offset, value):
    bytes = struct.pack(">I",value)
    data[offset:offset+4] = array.array('B',bytes)
