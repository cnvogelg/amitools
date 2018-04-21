import os.path

from amitools.binfmt.BinFmt import BinFmt
from amitools.binfmt.Relocate import Relocate
from amitools.vamos.label import LabelSegment
from .seglist import SegList


class SegmentLoader:

  def __init__(self, alloc):
    self.alloc = alloc
    self.mem = alloc.get_mem()
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

    # get info about segments to allocate
    sizes = relocator.get_sizes()
    names = bin_img.get_segment_names()
    bin_img_segs = bin_img.get_segments()

    # build label names
    if self.alloc.label_mgr:
      labels = []
      for i in xrange(len(sizes)):
        name = "%s_%d:%s" % (base_name, i, names[i].lower())
        labels.append(name)
    else:
      labels = None

    # allocate seg list
    seg_list = SegList.alloc(self.alloc, sizes, labels, bin_img_segs)

    # retrieve addr
    addrs = seg_list.get_all_addrs()

    # relocate to addresses and return data
    datas = relocator.relocate(addrs)

    # write contents to allocated memory
    for i in xrange(len(sizes)):
      # write data to segments
      self.mem.w_block(addrs[i], datas[i])

    return seg_list
