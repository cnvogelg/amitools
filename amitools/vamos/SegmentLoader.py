import os.path

from amitools import Hunk
from amitools.HunkReader import HunkReader
from amitools.HunkRelocate import HunkRelocate
from AccessMemory import AccessMemory
from LabelRange import LabelRange
from Log import *

class Segment:
  def __init__(self,name, addr, size, label):
    self.name = name
    self.addr = addr
    self.start = addr + 4
    self.size = size
    self.end = addr + size
    self.label = label
  def __str__(self):
    return "[Seg:'%s':%06x-%06x]" % (self.name, self.addr, self.end)

class SegList:
  def __init__(self, ami_bin_file, sys_bin_file):
    self.ami_bin_file = ami_bin_file
    self.sys_bin_file = sys_bin_file
    self.segments = []
    self.b_addr = 0
    self.prog_start = 0
    self.size = 0
    self.usage = 1
  
  def add(self, segment):
    if len(self.segments) == 0:
      self.b_addr = segment.addr >> 2
      self.prog_start = segment.addr + 4
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
  
  # load ami_bin_file
  def load_seg(self, ami_bin_file):
    # map file name
    sys_bin_file = self.path_mgr.ami_command_to_sys_path(ami_bin_file)
    if sys_bin_file == None:
      self.error = "failed mapping binary path: '%s'" % ami_bin_file
      return None

    # check if seg list already loaded in a parent process
    if self.loaded_seg_lists.has_key(sys_bin_file):
      seg_list = self.loaded_seg_lists[sys_bin_file]
      seg_list.usage += 1
      return seg_list

    # really load new seg list
    seg_list = self._load_seg(ami_bin_file,sys_bin_file)
    if seg_list == None:
      return None
    
    # store in cache
    self.loaded_seg_lists[sys_bin_file] = seg_list
    return seg_list
  
  # unload seg list
  def unload_seg(self, seg_list):
    sys_bin_file = seg_list.sys_bin_file
    # check that file is in cache
    if self.loaded_seg_lists.has_key(sys_bin_file):
      seg_list.usage -= 1
      # no more used
      if seg_list.usage == 0:
        del self.loaded_seg_lists[sys_bin_file]
        self._unload_seg(seg_list)
      return True
    else:
      self.error = "seglist not found in loaded seglists!"
      return False
  
  # load sys_bin_file
  def _load_seg(self, ami_bin_file, sys_bin_file):
    base_name = os.path.basename(sys_bin_file)
    hunk_file = HunkReader()
    
    # does file exist?
    if not os.path.isfile(sys_bin_file):
      self.error = "Can't find '%s'" % sys_bin_file
      return None
    
    # read hunk file
    fobj = file(sys_bin_file, "rb")
    result = hunk_file.read_file_obj(sys_bin_file,fobj,None)
    if result != Hunk.RESULT_OK:
      self.error = "Error loading '%s'" % sys_bin_file
      return None
      
    # build segments
    ok = hunk_file.build_segments()
    if not ok:
      self.error = "Error building segments for '%s'" % sys_bin_file
      return None
      
    # make sure its a loadseg()
    if hunk_file.type != Hunk.TYPE_LOADSEG:
      self.error = "File not loadSeg()able: '%s'" % sys_bin_file
      return None

    # create relocator
    relocator = HunkRelocate(hunk_file)
    
    # allocate segment memory
    sizes = relocator.get_sizes()
    names = relocator.get_type_names()
    seg_list = SegList(ami_bin_file,sys_bin_file)
    addrs = []
    for i in xrange(len(sizes)):
      size = sizes[i]
      seg_size = size + 4 # add segment pointer
      seg_addr = self.alloc.alloc_mem(seg_size)

      # create label
      label = None
      name = "%s_%d:%s" % (base_name,i,names[i].replace("HUNK_","").lower())
      if self.alloc.label_mgr != None:
        label = LabelRange(name, seg_addr, seg_size)
        self.alloc.label_mgr.add_label(label)

      seg = Segment(name, seg_addr, seg_size, label)
      seg_list.add(seg)
      addrs.append(seg.addr + 4) # begin of segment data/code
    
    # relocate to addresses and return data
    datas = relocator.relocate(addrs)
    
    # write to allocated memory
    last_addr = None
    for i in xrange(len(sizes)):
      addr = addrs[i]
      self.mem.access.w_data(addr, datas[i])
      # write segment pointers
      if last_addr != None:
        b_addr = addr >> 2 # BCPL segment pointers
        self.mem.access.w32(last_addr - 4, b_addr)
      last_addr = addr
    
    return seg_list
    
  def _unload_seg(self, seg_list):
    for seg in seg_list.segments:
      # free memory of segment
      self.alloc.free_mem(seg.addr, seg.size)
      # remove label of segment
      if self.alloc.label_mgr != None:
        self.alloc.label_mgr.remove_label(seg.label)
      