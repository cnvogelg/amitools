from .Exceptions import VamosInternalError
from .AmigaLibrary import AmigaLibrary
from .lib.lexec.ExecStruct import LibraryDef
import amitools.vamos.lib.LibList as LibList

class LibRegistry:
  def __init__(self, vamos_libs=None):
    # use default list
    if vamos_libs is None:
      vamos_libs = LibList.vamos_libs
    # state
    self.vamos_libs = vamos_libs
    # create name map
    self.name_map = {}
    for lib in vamos_libs:
      self.name_map[lib.name] = lib
    # map of open libs
    self.open_libs = {}

  def find_cls_by_name(self, name):
    """search a library by name and return its class"""
    if name in self.name_map:
      return self.name_map[name]

  def has_name(self, name):
    """test if a given name is available"""
    return name in self.name_map

  def get_all_cls(self):
    """return all registered lib classes"""
    return self.vamos_libs

  def get_all_names(self):
    """return all registered lib class names"""
    return map(lambda x: x.name, self.vamos_libs)

  def get_open_libs(self):
    return self.open_libs.values()

  def has_open_libs(self):
    return len(self.open_libs) > 0

  def open_lib(self, name, lib_cfg):
    """open a library and create instance of it"""
    # try to find class
    lib_cls = self.find_cls_by_name(name)
    if lib_cls is None:
      return None
    lib = lib_cls(lib_cfg)
    return self._int_open_lib(lib)

  def open_fake_lib(self, name, lib_cfg):
    """open an empty fake lib of given name"""
    # create generic lib
    lib = AmigaLibrary(name, LibraryDef, lib_cfg)
    return self._int_open_lib(lib)

  def _int_open_lib(self, lib):
    name = lib.name
    # only allow opening once
    if name in self.open_libs:
      raise VamosInternalError("Lib '%s' already opened!" % name)
    self.open_libs[name] = lib
    return lib

  def close_lib(self, lib):
    name = lib.name
    if name not in self.open_libs:
      raise VamosInternalError("Lib '%s' not opened!" % name)
    del self.open_libs[name]
