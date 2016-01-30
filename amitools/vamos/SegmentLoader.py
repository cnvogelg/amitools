import os.path

from amitools.binfmt.BinFmt import BinFmt
from amitools.binfmt.Relocate import Relocate
from AccessMemory import AccessMemory
from label.LabelSegment import LabelSegment
from Log import *

class Segment:
  def __init__(self, name, addr, size, label, bin_img_seg):
    self.name = name
    self.addr = addr
    self.start = addr + 8
    self.size = size
    self.end = addr + size
    self.label = label
    self.bin_img_seg = bin_img_seg

  def __str__(self):
    return "[Seg:'%s':%06x-%06x]" % (self.name, self.addr, self.end)

class SegList:
  def __init__(self, ami_bin_file, sys_bin_file, bin_img):
    self.ami_bin_file = ami_bin_file
    self.sys_bin_file = sys_bin_file
    self.bin_img = bin_img
    self.segments = []
    self.b_addr = 0
    self.prog_start = 0
    self.size = 0
    self.usage = 1

  def add(self, segment):
    if len(self.segments) == 0:
      self.b_addr = (segment.addr+4) >> 2 # baddr of 'next' ptr
      self.prog_start = segment.addr + 8 # begin of first code segment
    self.segments.append(segment)
    self.size += segment.size

  def __str__(self):
    return "[SegList:ami='%s':sys='%s':b_addr=%06x,prog=%06x,segs=#%d,size=%d,usage=%d]" % \
      (self.ami_bin_file, self.sys_bin_file, self.b_addr, self.prog_start, len(self.segments), self.size, self.usage)

class SegmentLoader:

  def __init__(self, mem, alloc, label_mgr, path_mgr):
    self.mem = mem
    self.alloc = alloc
    self.label_mgr = label_mgr
    self.path_mgr = path_mgr
    self.error = None
    self.loaded_seg_lists = {}
    self.binfmt = BinFmt()

  def can_load_seg(self, lock, ami_bin_file):
    return self.path_mgr.ami_command_to_sys_path(lock, ami_bin_file) != None

  # load ami_bin_file
  def load_seg(self, lock, ami_bin_file, allow_reuse = True, local_path = False):
    # map file name
    if local_path:
      sys_bin_file = self.path_mgr.ami_to_sys_path(lock,ami_bin_file,searchMulti=True)
    else:
      sys_bin_file = self.path_mgr.ami_command_to_sys_path(lock, ami_bin_file)
    if sys_bin_file == None:
      self.error = "failed mapping binary path: '%s'" % ami_bin_file
      return None

    # check if seg list already loaded in a parent process
    # Bummer! This cannot work unless commands are resident!
    if allow_reuse and self.loaded_seg_lists.has_key(sys_bin_file):
      seg_list = self.loaded_seg_lists[sys_bin_file]
      seg_list.usage += 1
      return seg_list

    # really load new seg list
    seg_list = self._load_seg(ami_bin_file,sys_bin_file)
    if seg_list == None:
      return None

    # store in cache if allowed by caller
    if allow_reuse:
      self.loaded_seg_lists[sys_bin_file] = seg_list
    return seg_list

  # unload seg list
  def unload_seg(self, seg_list, allow_reuse = True):
    sys_bin_file = seg_list.sys_bin_file
    # check that file is in cache
    if not allow_reuse or sys_bin_file in self.loaded_seg_lists:
      seg_list.usage -= 1
      # no more used
      if seg_list.usage == 0:
        if sys_bin_file in self.loaded_seg_lists:
          del self.loaded_seg_lists[sys_bin_file]
        self._unload_seg(seg_list)
      return True
    else:
      self.error = "seglist not found in loaded seglists!"
      return False

  # load sys_bin_file
  def _load_seg(self, ami_bin_file, sys_bin_file):
    base_name = os.path.basename(sys_bin_file)

    # does file exist?
    if not os.path.isfile(sys_bin_file):
      self.error = "Can't find '%s'" % sys_bin_file
      return None

    # try to load bin image in supported format (e.g. HUNK or ELF)
    try:
      bin_img = self.binfmt.load_image(sys_bin_file)
      if bin_img is None:
        self.error = "Error loading '%s': unsupported format" % sys_bin_file
        return None
    except Exception as e:
      self.error = "Error loading '%s': %s" % (sys_bin_file, e)
      return None

    # create relocator
    relocator = Relocate(bin_img)

    # allocate segment memory
    sizes = relocator.get_sizes()
    names = bin_img.get_segment_names()
    bin_img_segs = bin_img.get_segments()
    seg_list = SegList(ami_bin_file, sys_bin_file, bin_img)
    addrs = []
    for i in xrange(len(sizes)):
      size = sizes[i]
      seg_size = size + 8 # add segment pointer and size of segment
      seg_addr = self.alloc.alloc_mem(seg_size)

      # create label
      label = None
      name = "%s_%d:%s" % (base_name,i,names[i].lower())
      bin_img_seg = bin_img_segs[i]
      if self.alloc.label_mgr != None:
        label = LabelSegment(name, seg_addr, seg_size, bin_img_seg)
        self.alloc.label_mgr.add_label(label)

      seg = Segment(name, seg_addr, seg_size, label, bin_img_seg)
      seg_list.add(seg)
      addrs.append(seg.addr + 8) # begin of segment data/code

    # relocate to addresses and return data
    datas = relocator.relocate(addrs)

    # write to allocated memory
    last_addr = None
    for i in xrange(len(sizes)):
      # write data to segments
      addr = addrs[i]
      self.mem.access.w_data(addr, datas[i])
      # link segment pointers
      if last_addr != None:
        b_addr = (addr-4) >> 2 # BCPL segment 'next' pointer
        self.mem.access.w32(last_addr - 4, b_addr)
      # write size before segment pointer
      total_size = (sizes[i] + 8)
      self.mem.access.w32(addr - 8, total_size)
      last_addr = addr

    # clear final 'next' pointer
    self.mem.access.w32(addr - 4, 0)

    return seg_list

  def _unload_seg(self, seg_list):
    for seg in seg_list.segments:
      # free memory of segment
      self.alloc.free_mem(seg.addr, seg.size)
      # remove label of segment
      if self.alloc.label_mgr != None:
        self.alloc.label_mgr.remove_label(seg.label)

