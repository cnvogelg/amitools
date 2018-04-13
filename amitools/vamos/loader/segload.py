import os.path

from amitools.binfmt.BinFmt import BinFmt
from amitools.binfmt.Relocate import Relocate
from amitools.vamos.label import LabelSegment
from .seglist import SegList, Segment


class SegmentLoader:

  def __init__(self, mem, alloc):
    self.mem = mem
    self.alloc = alloc
    self.binfmt = BinFmt()

  # load sys_bin_file
  def load_seglist(self, sys_bin_file):
    base_name = os.path.basename(sys_bin_file)

    # does file exist?
    if not os.path.isfile(sys_bin_file):
      return None

    # try to load bin image in supported format (e.g. HUNK or ELF)
    bin_img = self.binfmt.load_image(sys_bin_file)
    if bin_img is None:
      return None

    # create relocator
    relocator = Relocate(bin_img)

    # allocate segment memory
    sizes = relocator.get_sizes()
    names = bin_img.get_segment_names()
    bin_img_segs = bin_img.get_segments()
    seg_list = SegList(sys_bin_file, bin_img)
    addrs = []
    for i in xrange(len(sizes)):
      size = sizes[i]
      seg_size = size + 8  # add segment pointer and size of segment
      seg_addr = self.alloc.alloc_mem(seg_size)

      # create label
      label = None
      name = "%s_%d:%s" % (base_name, i, names[i].lower())
      bin_img_seg = bin_img_segs[i]
      if self.alloc.label_mgr != None:
        label = LabelSegment(name, seg_addr, seg_size, bin_img_seg)
        self.alloc.label_mgr.add_label(label)

      seg = Segment(name, seg_addr, seg_size, label, bin_img_seg)
      seg_list.add(seg)
      addrs.append(seg.addr + 8)  # begin of segment data/code

    # relocate to addresses and return data
    datas = relocator.relocate(addrs)

    # write to allocated memory
    last_addr = None
    for i in xrange(len(sizes)):
      # write data to segments
      addr = addrs[i]
      self.mem.w_block(addr, datas[i])
      # link segment pointers
      if last_addr != None:
        b_addr = (addr-4) >> 2  # BCPL segment 'next' pointer
        self.mem.w32(last_addr - 4, b_addr)
      # write size before segment pointer
      total_size = (sizes[i] + 8)
      self.mem.w32(addr - 8, total_size)
      last_addr = addr

    # clear final 'next' pointer
    self.mem.w32(addr - 4, 0)

    return seg_list

  def unload_seglist(self, seg_list):
    for seg in seg_list.segments:
      # free memory of segment
      self.alloc.free_mem(seg.addr, seg.size)
      # remove label of segment
      if self.alloc.label_mgr:
        self.alloc.label_mgr.remove_label(seg.label)
