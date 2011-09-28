import array
import struct

from amitools import Hunk

class HunkRelocate:
  
  def __init__(self, hunk_file):
    self.hunk_file = hunk_file
    
  def get_sizes(self):
    sizes = []
    for segment in self.hunk_file.segments:
      main_hunk = segment[0]
      size = main_hunk['size']
      sizes.append(size)
    return sizes
  
  def get_seq_addrs(self, base_addr):
    sizes = self.get_sizes()
    addrs = []
    addr = base_addr
    for s in sizes:
      addrs.append(addr)
      addr += s
    return addrs
  
  def get_total_size(self):
    total = 0
    for segment in self.hunk_file.segments:
      main_hunk = segment[0]
      total += main_hunk['size']
    return total
  
  def relocate_one_block(self, addr):
    addrs = self.get_seq_addrs(addr)
    datas = self.relocate(addrs)
    return "".join(datas)
  
  def relocate(self, addr):
    datas = []
    for segment in self.hunk_file.segments:
      main_hunk = segment[0]
      if main_hunk.has_key('data'):
        data = array.array('B',main_hunk['data'])
      else: # bss
        data = array.array('B','\0' * main_hunk['size'])
      
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
              self.relocate32(data,offset,hunk_addr)          
        
      datas.append(data.tostring())
    return datas

  def relocate32(self, data, offset, hunk_addr):
    delta = self.read_long(data, offset)
    addr = hunk_addr + delta
    self.write_long(data, offset, addr)
    
  def read_long(self, data, offset):
    bytes = data[offset:offset+4]
    return struct.unpack(">I",bytes)[0]
  
  def write_long(self, data, offset, value):
    bytes = struct.pack(">I",value)
    data[offset:offset+4] = array.array('B',bytes)
