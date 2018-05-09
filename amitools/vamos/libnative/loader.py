from .initresident import InitRes
from amitools.vamos.atypes import Resident
from amitools.vamos.loader import SegmentLoader


class LibLoader(object):

  def __init__(self, machine, alloc, segloader=None):
    if segloader is None:
      segloader = SegmentLoader(alloc)
    self.machine = machine
    self.mem = machine.get_mem()
    self.alloc = alloc
    self.segloader = segloader
    self.initres = InitRes(machine, alloc)

  def load_lib(self, sys_bin_file, run_sp=None):
    """return lib_base addr or 0 plus seglist or 0"""
    # load seglist
    seglist = self.segloader.load_seglist(sys_bin_file)
    if not seglist:
      return 0, None
    # find resident in first hunk
    seg = seglist.get_segment()
    res = Resident.find(self.mem, seg.get_addr(), seg.get_size())
    if not res:
      seglist.free()
      return 0, None
    # init resident
    lib_base, mem_obj = self.initres.init_resident(
        res.get_addr(), seglist.get_baddr(), run_sp=run_sp)
    # unload seglist on error
    if lib_base == 0:
      seglist.free()
    return lib_base, seglist

  def load_lib_name(self, path_mgr, lib_name, lock=None, run_sp=None):
    # get search amiga paths
    search_paths = self.get_lib_search_paths(lib_name)
    # now try search paths
    for ami_path in search_paths:
      sys_path = path_mgr.ami_to_sys_path(lock, ami_path, mustExist=True)
      if sys_path:
        lib_base, seglist = self.load_lib(sys_path, run_sp)
        if lib_base != 0:
          return lib_base, seglist, sys_path, ami_path
    return 0, None, None, None

  @staticmethod
  def get_lib_base_name(lib_name):
    result = lib_name
    pos = result.rfind('/')
    if pos != -1:
      result = result[pos+1:]
    pos = result.rfind(':')
    if pos != -1:
      result = result[pos+1:]
    return result.lower()

  @staticmethod
  def get_lib_search_paths(lib_name, base_dir=None):
    """return list of Amiga paths where to search for library"""
    if base_dir is None:
      base_dir = "libs"
    # relative path
    if lib_name.find(':') == -1:
      base_name = base_dir + "/" + lib_name
      return [lib_name, base_name,
              "PROGDIR:" + lib_name, "PROGDIR:" + base_name,
              base_dir.upper() + ":" + lib_name]
    # absolute path
    else:
      return [lib_name]
