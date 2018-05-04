from .initresident import InitRes
from amitools.vamos.atypes import Resident


class LibLoader(object):

  def __init__(self, machine, alloc, segloader):
    self.machine = machine
    self.mem = machine.get_mem()
    self.alloc = alloc
    self.segloader = segloader
    self.initres = InitRes(machine, alloc)

  def load_lib(self, sys_bin_file, run_sp=None):
    """return lib_base addr or 0"""
    # load seglist
    seglist = self.segloader.load_seglist(sys_bin_file)
    if not seglist:
      return 0
    # find resident in first hunk
    seg = seglist.get_segment()
    res = Resident.find(self.mem, seg.get_addr(), seg.get_size())
    if not res:
      seglist.free()
      return 0
    # init resident
    lib_base, mem_obj = self.initres.init_resident(
      res.get_addr(), seglist.get_baddr(), run_sp=run_sp)
    # unload seglist on error
    if lib_base == 0:
      seglist.free()
    return lib_base
