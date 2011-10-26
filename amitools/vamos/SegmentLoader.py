import os.path

from amitools import Hunk
from amitools.HunkReader import HunkReader
from amitools.HunkRelocate import HunkRelocate
from AccessMemory import AccessMemory

class SegmentLoader:
  
  def __init__(self, alloc):
    self.alloc = alloc
    self.error = None
    
  def load_seg(self, name):
    base_name = os.path.basename(name)
    
    hunk_file = HunkReader()
    
    # read hunk file
    fobj = file(name, "rb")
    result = hunk_file.read_file_obj(name,fobj,None)
    if result != Hunk.RESULT_OK:
      self.error = "Error loading '%s'" % name
      return None
      
    # build segments
    ok = hunk_file.build_segments()
    if not ok:
      self.error = "Error building segments for '%s'" % name
      return None
      
    # make sure its a loadseg()
    if hunk_file.type != Hunk.TYPE_LOADSEG:
      self.error = "File not loadSeg()able: '%s'" % name
      return None

    # create relocator
    relocator = HunkRelocate(hunk_file)
    
    # allocate segment memory
    sizes = relocator.get_sizes()
    names = relocator.get_type_names()
    seg_list = []
    addrs = []
    for i in xrange(len(sizes)):
      size = sizes[i]
      name = "%s:%d:%s" % (base_name,i,names[i].replace("HUNK_","").lower())
      mem = self.alloc.alloc_memory(name, size)
      seg_list.append(mem)
      addrs.append(mem.addr)
    
    # relocate to addresses and return data
    datas = relocator.relocate(addrs)
    
    # write to allocated memory
    for i in xrange(len(sizes)):
      mem = seg_list[i]
      addr = addrs[i]
      am = AccessMemory(mem)
      am.w_data(addr, datas[i])
    
    return seg_list